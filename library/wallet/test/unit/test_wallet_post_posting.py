# standard libs
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

# library
import library.wallet.contracts.template.wallet as contract
from library.wallet.test.unit.test_wallet_common import (
    DEFAULT_DATETIME,
    DEFAULT_DENOMINATION,
    DEFAULT_NOMINATED_ACCOUNT,
    DUPLICATION,
    TODAYS_SPENDING,
    WalletTestBase,
)

# features
import library.features.common.fetchers as fetchers

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    BalanceDefaultDict,
    BalancesObservation,
    FlagTimeseries,
    PostPostingHookArguments,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    ACCOUNT_ID,
    DEFAULT_INTERNAL_ACCOUNT,
    DEFAULT_PHASE,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    CustomInstruction,
    Phase,
    Posting,
)


class PostPostingHookTest(WalletTestBase):
    def test_post_posting_code_duplicates_spending(self):
        initial_balance_amount = Decimal("200")
        balance_dict = {
            self.balance_coordinate(
                denomination=DEFAULT_DENOMINATION,
            ): self.balance(net=initial_balance_amount),
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

        test_posting_instruction = self.outbound_hard_settlement(
            amount=initial_balance_amount,
            denomination=DEFAULT_DENOMINATION,
            target_account_id=mock_vault.account_id,
            internal_account_id="1",
        )

        hook_arguments = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[test_posting_instruction],
            client_transactions={},
        )
        hook_result = contract.post_posting_hook(mock_vault, hook_arguments)
        result_pi_directive = hook_result.posting_instructions_directives[0]
        result_pi = result_pi_directive.posting_instructions[0]
        result_postings = result_pi.postings

        expected_postings = [
            Posting(
                denomination=DEFAULT_DENOMINATION,
                account_id=ACCOUNT_ID,
                account_address=DUPLICATION,
                asset=DEFAULT_ASSET,
                credit=True,
                amount=initial_balance_amount,
                phase=DEFAULT_PHASE,
            ),
            Posting(
                denomination=DEFAULT_DENOMINATION,
                account_id=ACCOUNT_ID,
                account_address=TODAYS_SPENDING,
                asset=DEFAULT_ASSET,
                credit=False,
                amount=initial_balance_amount,
                phase=DEFAULT_PHASE,
            ),
        ]

        expected_pi = CustomInstruction(
            postings=expected_postings,
            instruction_details={"description": "UPDATING_TRACKED_SPEND"},
            override_all_restrictions=None,
        )

        expected_value_timestamp = datetime(2019, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC"))
        self.assertEqual(result_pi_directive.value_datetime, expected_value_timestamp)
        self.assertEqual(result_postings, expected_postings)
        self.assertEqual(result_pi, expected_pi)

    def test_post_posting_code_doesnt_duplicate_spending_with_force_override_true(self):
        balance_dict = {
            self.balance_coordinate(
                denomination=DEFAULT_DENOMINATION,
            ): self.balance(net=Decimal(200)),
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

        test_postings = [
            Posting(
                credit=True,
                amount=Decimal("200"),
                denomination=DEFAULT_DENOMINATION,
                account_id="1",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
            Posting(
                credit=False,
                amount=Decimal("200"),
                denomination=DEFAULT_DENOMINATION,
                account_id=mock_vault.account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
        ]
        test_posting_instruction = CustomInstruction(
            postings=test_postings,
            instruction_details={"force_override": "true"},
            transaction_code=None,
            override_all_restrictions=False,
        )
        test_posting_instruction._set_output_attributes(
            committed_postings=test_postings,
            own_account_id=mock_vault.account_id,
            tside=contract.tside,
        )

        hook_arguments = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[test_posting_instruction],
            client_transactions={},
        )
        hook_result = contract.post_posting_hook(mock_vault, hook_arguments)

        self.assertIsNone(hook_result)

    def test_post_posting_code_duplicates_release_with_force_override_true(self):
        initial_balance_amount = Decimal("200")
        small_amount = Decimal("10")

        balance_dict = {
            self.balance_coordinate(
                denomination=DEFAULT_DENOMINATION,
            ): self.balance(net=initial_balance_amount),
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

        test_posting_instruction = self.release_outbound_auth(
            unsettled_amount=small_amount,
            client_transaction_id="test",
            denomination=DEFAULT_DENOMINATION,
            target_account_id=mock_vault.account_id,
            instruction_details={"force_override": "true"},
        )

        hook_arguments = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[test_posting_instruction],
            client_transactions={},
        )

        hook_result = contract.post_posting_hook(mock_vault, hook_arguments)
        result_pi_directive = hook_result.posting_instructions_directives[0]
        result_pi = result_pi_directive.posting_instructions[0]
        result_postings = result_pi.postings

        expected_postings = [
            Posting(
                denomination=DEFAULT_DENOMINATION,
                account_id=ACCOUNT_ID,
                account_address=TODAYS_SPENDING,
                asset=DEFAULT_ASSET,
                credit=True,
                amount=small_amount,
                phase=DEFAULT_PHASE,
            ),
            Posting(
                denomination=DEFAULT_DENOMINATION,
                account_id=ACCOUNT_ID,
                account_address=DUPLICATION,
                asset=DEFAULT_ASSET,
                credit=False,
                amount=small_amount,
                phase=DEFAULT_PHASE,
            ),
        ]

        expected_value_timestamp = datetime(2019, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC"))
        self.assertEqual(result_pi_directive.value_datetime, expected_value_timestamp)
        self.assertEqual(result_postings, expected_postings)

    def test_post_posting_code_sweeps_over_balance(self):
        initial_balance_amount = Decimal("10000")

        balance_dict = {
            self.balance_coordinate(
                denomination=DEFAULT_DENOMINATION,
            ): self.balance(net=initial_balance_amount),
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

        test_posting_instruction = self.inbound_hard_settlement(
            amount=initial_balance_amount,
            denomination=DEFAULT_DENOMINATION,
            target_account_id=mock_vault.account_id,
            internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
        )

        hook_arguments = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[test_posting_instruction],
            client_transactions={},
        )

        hook_result = contract.post_posting_hook(mock_vault, hook_arguments)
        result_pi_directive = hook_result.posting_instructions_directives[0]
        result_pi = result_pi_directive.posting_instructions[0]
        result_postings = result_pi.postings

        expected_postings = [
            Posting(
                denomination=DEFAULT_DENOMINATION,
                account_id=DEFAULT_NOMINATED_ACCOUNT,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                amount=Decimal(9000),
                phase=DEFAULT_PHASE,
            ),
            Posting(
                denomination=DEFAULT_DENOMINATION,
                account_id=ACCOUNT_ID,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                amount=Decimal(9000),
                phase=DEFAULT_PHASE,
            ),
        ]

        expected_value_timestamp = datetime(2019, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC"))
        self.assertEqual(result_pi_directive.value_datetime, expected_value_timestamp)
        self.assertEqual(result_postings, expected_postings)

    def test_post_posting_auto_top_up_true(self):
        previous_balance_amount = Decimal(20)
        spend_amount = -Decimal(100)
        # For this test case the auto top up flag is true and because the spend is over
        # the wallet balance, current_balance_amount is expected to be negative
        # for the live BOF. The transfer amount in postings needs to be positive.
        current_balance_amount = previous_balance_amount + spend_amount
        transfer_amount = -current_balance_amount

        balance_dict = {
            self.balance_coordinate(
                denomination=DEFAULT_DENOMINATION,
            ): self.balance(net=current_balance_amount),
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
            flags_ts={"AUTO_TOP_UP_WALLET": FlagTimeseries([(DEFAULT_DATETIME, True)])},
        )

        test_posting_instruction = self.outbound_hard_settlement(
            amount=abs(spend_amount),
            denomination=DEFAULT_DENOMINATION,
            target_account_id=mock_vault.account_id,
            internal_account_id="1",
        )

        expected_postings = [
            Posting(
                denomination=DEFAULT_DENOMINATION,
                account_id=ACCOUNT_ID,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                amount=transfer_amount,
                phase=DEFAULT_PHASE,
            ),
            Posting(
                denomination=DEFAULT_DENOMINATION,
                account_id=DEFAULT_NOMINATED_ACCOUNT,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                amount=transfer_amount,
                phase=DEFAULT_PHASE,
            ),
        ]

        expected_pi = CustomInstruction(
            postings=expected_postings,
            instruction_details={
                "description": "Auto top up transferred from nominated account:80"
            },
            override_all_restrictions=None,
        )

        hook_arguments = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[test_posting_instruction],
            client_transactions={},
        )
        hook_result = contract.post_posting_hook(mock_vault, hook_arguments)
        result_pi_directive = hook_result.posting_instructions_directives[0]
        result_pi = result_pi_directive.posting_instructions[0]
        result_postings = result_pi.postings

        expected_value_timestamp = datetime(2019, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC"))
        self.assertEqual(result_pi_directive.value_datetime, expected_value_timestamp)
        self.assertEqual(result_postings, expected_postings)
        self.assertEqual(result_pi, expected_pi)

    def test_post_posting_code_doesnt_duplicate_spending_with_refund(self):
        balance_dict = {
            self.balance_coordinate(
                denomination=DEFAULT_DENOMINATION,
            ): self.balance(net=Decimal(200)),
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

        test_posting_instruction = self.inbound_hard_settlement(
            amount=Decimal("100"),
            denomination=DEFAULT_DENOMINATION,
            target_account_id=mock_vault.account_id,
            internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
            instruction_details={"refund": "True"},
        )

        hook_arguments = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[test_posting_instruction],
            client_transactions={},
        )
        hook_result = contract.post_posting_hook(mock_vault, hook_arguments)
        result_pi_directive = hook_result.posting_instructions_directives[0]
        result_pi = result_pi_directive.posting_instructions[0]
        result_postings = result_pi.postings

        expected_postings = [
            Posting(
                credit=True,
                amount=Decimal("100"),
                denomination=DEFAULT_DENOMINATION,
                account_id=mock_vault.account_id,
                account_address=TODAYS_SPENDING,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
            Posting(
                credit=False,
                amount=Decimal("100"),
                denomination=DEFAULT_DENOMINATION,
                account_id=mock_vault.account_id,
                account_address=DUPLICATION,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
        ]

        self.assertEqual(result_postings, expected_postings)

    def test_post_posting_code_doesnt_duplicate_spending_with_nominated_acct_transfer(self):
        balance_dict = {
            self.balance_coordinate(
                denomination=DEFAULT_DENOMINATION,
            ): self.balance(net=Decimal(200)),
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

        test_posting_instruction = self.outbound_transfer(
            amount=Decimal("200"),
            denomination=DEFAULT_DENOMINATION,
            creditor_target_account_id="1",
            debtor_target_account_id=mock_vault.account_id,
            instruction_details={"withdrawal_to_nominated_account": "True"},
            transaction_code=None,
            override_all_restrictions=False,
        )

        hook_arguments = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[test_posting_instruction],
            client_transactions={},
        )
        hook_result = contract.post_posting_hook(mock_vault, hook_arguments)

        self.assertIsNone(hook_result)
