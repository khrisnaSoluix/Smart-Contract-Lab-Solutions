# standard libs
from decimal import Decimal

# library
import library.wallet.contracts.template.wallet as contract
from library.wallet.test.unit.test_wallet_common import (
    DEFAULT_DATETIME,
    DEFAULT_DENOMINATION,
    DUPLICATION,
    TODAYS_SPENDING,
    WalletTestBase,
)

# features
import library.features.common.fetchers as fetchers

# contracts api
from contracts_api import DEFAULT_ADDRESS, DEFAULT_ASSET, ScheduledEventHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    ACCOUNT_ID,
    DEFAULT_PHASE,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    BalanceDefaultDict,
    BalancesObservation,
    CustomInstruction,
    Posting,
    PostingInstructionsDirective,
)


class ScheduledEventHookTest(WalletTestBase):
    def test_scheduled_event_hook_zeros_out_daily_spend(self):
        default_committed = Decimal("200")
        todays_spending = Decimal("-100")
        balance_dict = {
            self.balance_coordinate(
                account_address=TODAYS_SPENDING,
            ): self.balance(net=todays_spending),
            self.balance_coordinate(account_address=DEFAULT_ADDRESS): self.balance(
                net=-default_committed
            ),
        }
        balances_observation = BalancesObservation(
            balances=BalanceDefaultDict(mapping=balance_dict),
            value_datetime=DEFAULT_DATETIME,
        )
        mapping = {fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: balances_observation}

        mock_vault = self.create_mock(balances_observation_fetchers_mapping=mapping)

        postings = [
            Posting(
                credit=True,
                amount=Decimal("100"),
                denomination=DEFAULT_DENOMINATION,
                account_id=ACCOUNT_ID,
                account_address=TODAYS_SPENDING,
                asset=DEFAULT_ASSET,
                phase=DEFAULT_PHASE,
            ),
            Posting(
                credit=False,
                amount=Decimal("100"),
                denomination=DEFAULT_DENOMINATION,
                account_id=ACCOUNT_ID,
                account_address=DUPLICATION,
                asset=DEFAULT_ASSET,
                phase=DEFAULT_PHASE,
            ),
        ]

        expected_pis = CustomInstruction(
            postings=postings,
            instruction_details={
                "event_type": "ZERO_OUT_DAILY_SPENDING",
            },
            transaction_code=None,
            override_all_restrictions=True,
        )

        expected_pid_list = [
            PostingInstructionsDirective(
                posting_instructions=[expected_pis],
                client_batch_id="ZERO_OUT_DAILY_SPENDING-MOCK_HOOK",
                value_datetime=DEFAULT_DATETIME,
            )
        ]

        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type="ZERO_OUT_DAILY_SPEND",
            pause_at_datetime=None,
        )

        hook_result = contract.scheduled_event_hook(mock_vault, hook_arguments)
        result_pid_list = hook_result.posting_instructions_directives

        for result_pid, expected_pid in list(zip(result_pid_list, expected_pid_list)):
            self.assertEqual(result_pid, expected_pid)

    def test_scheduled_event_hook_event_type_not_found(self):
        mock_vault = self.create_mock()

        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type="",
        )

        hook_result = contract.scheduled_event_hook(mock_vault, hook_arguments)

        self.assertIsNone(hook_result)
