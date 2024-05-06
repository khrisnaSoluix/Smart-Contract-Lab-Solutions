# standard libs
from decimal import Decimal

# library
import library.wallet.contracts.template.wallet as contract
from library.wallet.test.unit.test_wallet_common import (
    DEFAULT_DATETIME,
    DEFAULT_DENOMINATION,
    DEFAULT_NOMINATED_ACCOUNT,
    WalletTestBase,
)

# features
import library.features.common.fetchers as fetchers

# contracts api
from contracts_api import DEFAULT_ADDRESS, DEFAULT_ASSET, PostParameterChangeHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    BalanceDefaultDict,
    BalancesObservation,
    CustomInstruction,
    Phase,
    Posting,
    PostingInstructionsDirective,
    PostParameterChangeHookResult,
)


class PostParameterChangeHookTest(WalletTestBase):
    def test_post_parameter_change_hook_no_sweep_customer_limit(self):
        "Changing a customer wallet limit down, with 0 balances, doesn't cause a sweep"
        balance_dict = {
            self.balance_coordinate(): self.balance(net=Decimal(0)),
        }
        balances_observation = BalancesObservation(
            balances=BalanceDefaultDict(mapping=balance_dict),
            value_datetime=DEFAULT_DATETIME,
        )
        mapping = {fetchers.LIVE_BALANCES_BOF_ID: balances_observation}

        mock_vault = self.create_mock(balances_observation_fetchers_mapping=mapping)
        hook_arguments = PostParameterChangeHookArguments(
            old_parameter_values={"customer_wallet_limit": Decimal("1000")},
            updated_parameter_values={"customer_wallet_limit": Decimal("500")},
            effective_datetime=DEFAULT_DATETIME,
        )
        hook_result = contract.post_parameter_change_hook(mock_vault, hook_arguments)
        self.assertIsNone(hook_result)

    def test_post_parameter_change_hook_sweep_customer_limit(self):
        """
        Changing a customer wallet limit down, with balances > new limit,
        causes a sweep.
        """
        initial_balance_amount = Decimal("1000")
        lowered_limit = Decimal("500")
        delta = initial_balance_amount - lowered_limit

        balance_dict = {
            self.balance_coordinate(): self.balance(net=initial_balance_amount),
        }
        balances_observation = BalancesObservation(
            balances=BalanceDefaultDict(mapping=balance_dict),
            value_datetime=DEFAULT_DATETIME,
        )
        mapping = {fetchers.LIVE_BALANCES_BOF_ID: balances_observation}

        mock_vault = self.create_mock(balances_observation_fetchers_mapping=mapping)

        hook_arguments = PostParameterChangeHookArguments(
            old_parameter_values={"customer_wallet_limit": initial_balance_amount},
            updated_parameter_values={"customer_wallet_limit": lowered_limit},
            effective_datetime=DEFAULT_DATETIME,
        )
        hook_result = contract.post_parameter_change_hook(mock_vault, hook_arguments)

        expected_postings = [
            Posting(
                credit=True,
                amount=delta,
                denomination=DEFAULT_DENOMINATION,
                account_id=DEFAULT_NOMINATED_ACCOUNT,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
            Posting(
                credit=False,
                amount=delta,
                denomination=DEFAULT_DENOMINATION,
                account_id=mock_vault.account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
        ]
        expected_pid = PostingInstructionsDirective(
            posting_instructions=[
                CustomInstruction(
                    postings=expected_postings,
                    instruction_details={"description": "RETURNING_EXCESS_BALANCE"},
                    transaction_code=None,
                    override_all_restrictions=True,
                )
            ],
            value_datetime=DEFAULT_DATETIME,
        )
        expected_hook_result = PostParameterChangeHookResult(
            posting_instructions_directives=[expected_pid]
        )

        self.assertEqual(hook_result, expected_hook_result)

    def test_post_parameter_change_hook_no_sweep_customer_limit_if_new_limit_gt(self):
        """
        Changing a customer wallet limit up, with balances < new limit,
        does not cause a sweep.
        """
        initial_balance_amount = Decimal("1000")
        lowered_limit = Decimal("1500")

        balance_dict = {
            self.balance_coordinate(): self.balance(net=initial_balance_amount),
        }
        balances_observation = BalancesObservation(
            balances=BalanceDefaultDict(mapping=balance_dict),
            value_datetime=DEFAULT_DATETIME,
        )
        mapping = {fetchers.LIVE_BALANCES_BOF_ID: balances_observation}

        mock_vault = self.create_mock(balances_observation_fetchers_mapping=mapping)

        hook_arguments = PostParameterChangeHookArguments(
            old_parameter_values={"customer_wallet_limit": initial_balance_amount},
            updated_parameter_values={"customer_wallet_limit": lowered_limit},
            effective_datetime=DEFAULT_DATETIME,
        )
        hook_result = contract.post_parameter_change_hook(mock_vault, hook_arguments)

        self.assertIsNone(hook_result)

    def test_post_parameter_change_hook_no_sweep_customer_limit_if_different_param_changed(self):
        """
        Changing a parameter other than customer wallet does not cause a sweep.
        """
        initial_balance_amount = Decimal("1000")
        balance_dict = {
            self.balance_coordinate(): self.balance(net=initial_balance_amount),
        }
        balances_observation = BalancesObservation(
            balances=BalanceDefaultDict(mapping=balance_dict),
            value_datetime=DEFAULT_DATETIME,
        )
        mapping = {fetchers.LIVE_BALANCES_BOF_ID: balances_observation}

        mock_vault = self.create_mock(balances_observation_fetchers_mapping=mapping)

        hook_arguments = PostParameterChangeHookArguments(
            old_parameter_values={"nominated_account": "1"},
            updated_parameter_values={"nominated_account": "2"},
            effective_datetime=DEFAULT_DATETIME,
        )
        hook_result = contract.post_parameter_change_hook(mock_vault, hook_arguments)

        self.assertIsNone(hook_result)
