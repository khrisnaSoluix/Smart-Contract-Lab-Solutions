# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# library
import library.time_deposit.contracts.template.time_deposit as time_deposit
from library.time_deposit.test import dimensions, files, parameters
from library.time_deposit.test.e2e import accounts as e2e_accounts, parameters as e2e_parameters

# inception sdk
from inception_sdk.test_framework import endtoend
from inception_sdk.test_framework.common.utils import ac_coverage
from inception_sdk.test_framework.endtoend.contracts_helper import ContractNotificationResourceType

endtoend.testhandle.CONTRACTS = {
    "time_deposit": {
        "path": files.TIME_DEPOSIT_CONTRACT,
        "template_params": e2e_parameters.default_renewed_template,
    },
}
endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = e2e_accounts.internal_accounts_tside

endtoend.testhandle.CALENDARS = {
    "PUBLIC_HOLIDAYS": ("library/common/calendars/public_holidays.resource.yaml")
}


class TimeDepositTest(endtoend.End2Endtest):
    @ac_coverage(["CPP-2083-AC06"])
    def test_full_withdrawal_during_grace_period(self):
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

        # withdraw all funds
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            amount="1000",
            account_id=time_deposit_id,
            denomination=parameters.TEST_DENOMINATION,
            client_batch_id="withdraw_all_funds",
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])
        endtoend.balances_helper.wait_for_account_balances(
            account_id=time_deposit_id,
            expected_balances=[
                (dimensions.DEFAULT, "0"),
                (dimensions.APPLIED_INTEREST_TRACKER, "0"),
                (dimensions.EARLY_WITHDRAWALS_TRACKER, "0"),
            ],
        )

        # full withdrawal incurs no fees during Grace Period
        endtoend.contracts_helper.wait_for_contract_notification(
            notification_type=time_deposit.WITHDRAWAL_FEES_NOTIFICATION,
            notification_details={
                "account_id": str(time_deposit_id),
                "withdrawal_amount": "1000",
                "denomination": "GBP",
                "flat_fee_amount": "0",
                "percentage_fee_amount": "0",
                "number_of_interest_days_fee": "0",
                "total_fee_amount": "0",
                "client_batch_id": "withdraw_all_funds",
            },
            resource_id=time_deposit_id,
            resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
        )

    def test_updating_term_parameter_within_grace_period(self):
        customer_id = endtoend.core_api_helper.create_customer()
        instance_params = {
            **e2e_parameters.default_instance,
        }

        td_account_id = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="time_deposit",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
            wait_for_activation=True,
        )["id"]
        term_before_request = endtoend.contracts_helper.get_account(td_account_id)[
            "instance_param_vals"
        ]["term"]
        self.assertEqual(term_before_request, "4")

        parameter_update_id = endtoend.core_api_helper.update_account_instance_parameters(
            account_id=td_account_id,
            instance_param_vals={"term": "24"},
        )["id"]
        endtoend.accounts_helper.wait_for_account_update(account_update_id=parameter_update_id)

        term_after_request = endtoend.contracts_helper.get_account(td_account_id)[
            "instance_param_vals"
        ]["term"]
        self.assertEqual(term_after_request, "24")
