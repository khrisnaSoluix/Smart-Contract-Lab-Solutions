# standard libs
from decimal import Decimal

# library
import library.wallet.contracts.template.wallet as contract
from library.wallet.test.unit.test_wallet_common import (
    DEFAULT_DATETIME,
    DEFAULT_DENOMINATION,
    WalletTestBase,
)

# features
import library.features.common.fetchers as fetchers

# contracts api
from contracts_api import (
    BalanceDefaultDict,
    BalancesObservation,
    FlagTimeseries,
    PrePostingHookArguments,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    RejectionReason,
)


class PrePostingHookTest(WalletTestBase):
    def test_posting_batch_with_additional_denom_and_sufficient_balance_is_accepted(
        self,
    ):
        gbp_posting = self.outbound_hard_settlement(amount=Decimal("30"), denomination="GBP")

        balance_dict = {
            self.balance_coordinate(
                denomination="GBP",
            ): self.balance(net=Decimal(100)),
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

        hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[gbp_posting],
            client_transactions={},
        )
        hook_result = contract.pre_posting_hook(mock_vault, hook_arguments)
        self.assertIsNone(hook_result)

    def test_posting_batch_with_additional_denom_and_sufficient_balances_is_accepted(
        self,
    ):
        usd_posting = self.outbound_hard_settlement(amount=Decimal("20"), denomination="USD")
        gbp_posting = self.outbound_hard_settlement(amount=Decimal("30"), denomination="GBP")

        balance_dict = {
            self.balance_coordinate(
                denomination="GBP",
            ): self.balance(net=Decimal(100)),
            self.balance_coordinate(
                denomination="USD",
            ): self.balance(net=Decimal(100)),
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

        hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[usd_posting, gbp_posting],
            client_transactions={},
        )
        hook_result = contract.pre_posting_hook(mock_vault, hook_arguments)
        self.assertIsNone(hook_result)

    def test_posting_batch_with_single_denom_rejected_if_insufficient_balances(self):
        usd_posting = self.outbound_hard_settlement(amount=Decimal("20"), denomination="USD")

        balance_dict = {
            self.balance_coordinate(
                denomination="USD",
            ): self.balance(net=Decimal(10)),
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

        hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[usd_posting],
            client_transactions={},
        )
        hook_result = contract.pre_posting_hook(mock_vault, hook_arguments)
        self.assertIsNotNone(hook_result)
        self.assertEqual(
            hook_result.rejection.message,
            "Postings total USD -20, which exceeds the available balance of USD 10",
        )
        self.assertEqual(hook_result.rejection.reason_code, RejectionReason.INSUFFICIENT_FUNDS)

    def test_posting_batch_with_supported_and_unsupported_denom_is_rejected(self):
        hkd_posting = self.outbound_hard_settlement(denomination="HKD", amount=Decimal(1))
        usd_posting = self.outbound_hard_settlement(denomination="USD", amount=Decimal(1))
        zar_posting = self.outbound_hard_settlement(denomination="ZAR", amount=Decimal(1))
        gbp_posting = self.outbound_hard_settlement(denomination="GBP", amount=Decimal(1))

        balance_dict = {
            self.balance_coordinate(
                denomination="USD",
            ): self.balance(net=Decimal(0)),
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

        hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[hkd_posting, usd_posting, zar_posting, gbp_posting],
            client_transactions={},
        )
        hook_result = contract.pre_posting_hook(mock_vault, hook_arguments)
        self.assertIsNotNone(hook_result)
        self.assertEqual(
            hook_result.rejection.message, "Postings received in unauthorised denominations"
        )
        self.assertEqual(hook_result.rejection.reason_code, RejectionReason.WRONG_DENOMINATION)

    def test_posting_batch_with_single_unsupported_denom_is_rejected(self):
        posting = self.outbound_hard_settlement(denomination="HKD", amount=Decimal(1))

        balance_dict = {
            self.balance_coordinate(
                denomination="USD",
            ): self.balance(net=Decimal(0)),
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

        hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[posting],
            client_transactions={},
        )
        hook_result = contract.pre_posting_hook(mock_vault, hook_arguments)
        self.assertIsNotNone(hook_result)
        self.assertEqual(
            hook_result.rejection.message, "Postings received in unauthorised denominations"
        )
        self.assertEqual(hook_result.rejection.reason_code, RejectionReason.WRONG_DENOMINATION)

    def test_pre_posting_no_money_flag_false(self):
        posting = self.outbound_hard_settlement(
            denomination=DEFAULT_DENOMINATION, amount=Decimal("100")
        )

        balance_dict = {
            self.balance_coordinate(
                denomination=DEFAULT_DENOMINATION,
            ): self.balance(net=Decimal(0)),
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

        hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[posting],
            client_transactions={},
        )
        hook_result = contract.pre_posting_hook(mock_vault, hook_arguments)
        self.assertIsNotNone(hook_result)
        self.assertEqual(hook_result.rejection.reason_code, RejectionReason.INSUFFICIENT_FUNDS)

    def test_pre_posting_no_money_flag_true(self):
        posting = self.outbound_hard_settlement(
            denomination=DEFAULT_DENOMINATION, amount=Decimal("100")
        )

        balance_dict = {
            self.balance_coordinate(
                denomination=DEFAULT_DENOMINATION,
            ): self.balance(net=Decimal(0)),
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

        hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[posting],
            client_transactions={},
        )
        hook_result = contract.pre_posting_hook(mock_vault, hook_arguments)
        self.assertIsNone(hook_result)

    def test_pre_posting_code_rejects_if_over_limit(self):
        posting = self.outbound_hard_settlement(
            denomination=DEFAULT_DENOMINATION, amount=Decimal("200")
        )

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
            balances_observation_fetchers_mapping=balances_observation_fetchers_mapping
        )

        hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[posting],
            client_transactions={},
        )
        hook_result = contract.pre_posting_hook(mock_vault, hook_arguments)
        self.assertIsNotNone(hook_result)
        self.assertEqual(hook_result.rejection.reason_code, RejectionReason.AGAINST_TNC)

    def test_pre_posting_code_ignores_limits_with_withdrawal_override_true(self):
        posting = self.outbound_hard_settlement(
            denomination=DEFAULT_DENOMINATION,
            amount=Decimal("99"),
            instruction_details={"withdrawal_override": "true"},
        )

        balance_dict = {
            self.balance_coordinate(
                denomination=DEFAULT_DENOMINATION,
            ): self.balance(net=Decimal(98)),
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

        hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[posting],
            client_transactions={},
        )
        hook_result = contract.pre_posting_hook(mock_vault, hook_arguments)
        self.assertIsNone(hook_result)

    def test_pre_posting_code_is_force_override_true(self):
        posting = self.outbound_hard_settlement(
            amount=Decimal("10"),
            instruction_details={"force_override": "true"},
        )

        balance_dict = {
            self.balance_coordinate(): self.balance(net=Decimal("5")),
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

        hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[posting],
            client_transactions={},
        )
        hook_result = contract.pre_posting_hook(mock_vault, hook_arguments)
        self.assertIsNone(hook_result)
