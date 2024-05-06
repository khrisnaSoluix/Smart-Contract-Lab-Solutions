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
from contracts_api import DEFAULT_ASSET, DeactivationHookArguments

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


class DeactivationHookTest(WalletTestBase):
    def test_deactivation_hook_zeros_daily_spend_amount(self):
        balance_amount = Decimal("-100")
        balance_dict = {
            self.balance_coordinate(
                account_address=TODAYS_SPENDING,
            ): self.balance(net=balance_amount),
            self.balance_coordinate(account_address=DUPLICATION): self.balance(net=-balance_amount),
        }
        balances_observation = BalancesObservation(
            balances=BalanceDefaultDict(mapping=balance_dict),
            value_datetime=DEFAULT_DATETIME,
        )
        balances_observation_fetchers_mapping = {
            fetchers.LIVE_BALANCES_BOF_ID: balances_observation
        }

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=balances_observation_fetchers_mapping,
        )

        hook_arguments = DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        hook_result = contract.deactivation_hook(mock_vault, hook_arguments)

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

        expected_pis = [
            CustomInstruction(
                postings=postings,
                instruction_details={
                    "event_type": "ZERO_OUT_DAILY_SPENDING",
                },
                transaction_code=None,
                override_all_restrictions=True,
            )
        ]

        expected_pid_list = [
            PostingInstructionsDirective(
                posting_instructions=expected_pis,
                client_batch_id="ZERO_OUT_DAILY_SPENDING-MOCK_HOOK",
                value_datetime=DEFAULT_DATETIME,
            )
        ]
        result_pid_list = hook_result.posting_instructions_directives
        for result_pid, expected_pid in list(zip(result_pid_list, expected_pid_list)):
            self.assertEqual(result_pid, expected_pid)

    def test_deactivation_hook_no_daily_spending(self):
        balance_dict = {
            self.balance_coordinate(): self.balance(net=Decimal(0)),
        }
        balances_observation = BalancesObservation(
            balances=BalanceDefaultDict(mapping=balance_dict),
            value_datetime=DEFAULT_DATETIME,
        )
        balances_observation_fetchers_mapping = {
            fetchers.LIVE_BALANCES_BOF_ID: balances_observation
        }

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=balances_observation_fetchers_mapping,
        )

        hook_arguments = DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        hook_result = contract.deactivation_hook(mock_vault, hook_arguments)

        self.assertIsNone(hook_result)

    def test_deactivation_hook_on_default_address_amount(self):
        default_balance = Decimal("100")
        balance_dict = {
            self.balance_coordinate(): self.balance(net=default_balance),
        }
        balances_observation = BalancesObservation(
            balances=BalanceDefaultDict(mapping=balance_dict),
            value_datetime=DEFAULT_DATETIME,
        )
        balances_observation_fetchers_mapping = {
            fetchers.LIVE_BALANCES_BOF_ID: balances_observation
        }

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=balances_observation_fetchers_mapping,
        )

        hook_arguments = DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        hook_result = contract.deactivation_hook(mock_vault, hook_arguments)

        self.assertIsNone(hook_result)
