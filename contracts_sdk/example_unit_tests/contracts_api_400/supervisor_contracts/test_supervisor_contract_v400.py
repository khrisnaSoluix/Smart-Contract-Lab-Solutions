from datetime import datetime
from decimal import Decimal
from unittest import mock, TestCase
from zoneinfo import ZoneInfo

from contracts_api import supervisor_contracts_lib  # type: ignore
from contracts_api import (
    SupervisorPostPostingHookArguments,
    OutboundAuthorisation,
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    Posting,
    Phase,
    ClientTransaction,
    Tside,
)

from . import supervisor_contract_v400


class SupervisorTestCase(TestCase):
    @staticmethod
    def _create_outbound_authorisation(account_id):
        instruction = OutboundAuthorisation(
            client_transaction_id="42",
            target_account_id=account_id,
            internal_account_id="1",
            amount=Decimal("10"),
            denomination="GBP",
            advice=True,
        )
        instruction._set_output_attributes(  # noqa: SLF001
            insertion_datetime=datetime(2002, 2, 2, tzinfo=ZoneInfo("UTC")),
            value_datetime=datetime(2002, 2, 2, tzinfo=ZoneInfo("UTC")),
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=[
                Posting(
                    account_id=account_id,
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    credit=False,
                    phase=Phase.PENDING_OUT,
                    amount=Decimal("10"),
                    denomination="GBP",
                ),
            ],
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_42",
            own_account_id=account_id,
            tside=Tside.LIABILITY,
        )
        return instruction

    def test_post_posting_hook_supervisor(self):
        # Define data values for the vault mocks
        effective_datetime = datetime(year=2020, month=2, day=15, tzinfo=ZoneInfo("UTC"))
        instruction = self._create_outbound_authorisation("supervisee_acc_id")
        ctx = ClientTransaction(
            client_transaction_id="42",
            account_id="supervisee_acc_id",
            posting_instructions=[instruction],
            tside=Tside.LIABILITY,
        )
        hook_arguments = SupervisorPostPostingHookArguments(
            effective_datetime=effective_datetime,
            supervisee_posting_instructions={"supervisee_acc_id": [instruction]},
            supervisee_client_transactions={"supervisee_acc_id": {"CoreContracts_42": ctx}},
        )
        # Create and mock the vault
        vault = mock.create_autospec(supervisor_contracts_lib.VaultFunctionsABC)
        # Call the plan post posting hook
        response = supervisor_contract_v400.post_posting_hook(vault, hook_arguments)
        # Assert on the hook results and vault method calls
        directives = response.supervisee_account_notification_directives["test_account_id"]
        self.assertEqual(1, len(directives))
        expected_type = "test"
        self.assertEqual(expected_type, directives[0].notification_type)
        self.assertEqual("PST", directives[0].notification_details["tz"])
        self.assertEqual("-10", directives[0].notification_details["postings_net_balance"])
