# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.deposit.transaction_limits.test.test_common_transaction_limit import (
    CommonTransactionLimitTest,
)
from library.features.v4.deposit.transaction_limits.withdrawal_limits import minimum_balance_by_tier

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DENOMINATION
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    BalancesObservation,
    Rejection,
    RejectionReason,
)


class TestMinimumBalanceByTier(CommonTransactionLimitTest):
    @patch.object(minimum_balance_by_tier.utils, "get_parameter")
    @patch.object(minimum_balance_by_tier.account_tiers, "get_account_tier")
    @patch.object(
        minimum_balance_by_tier.account_tiers, "get_tiered_parameter_value_based_on_account_tier"
    )
    def test_account_tier_minimum_balance_exceeded(
        self,
        mock_get_tiered_parameter_value_based_on_account_tier: MagicMock,
        mock_get_account_tier: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # Current balance is 100 so any withdrawal should be Rejection for SAVINGS account
        posting_instructions = [self.outbound_hard_settlement(amount=Decimal("1"))]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"tiered_minimum_balance_threshold": {"STANDARD": "0", "SAVINGS": "100"}}
        )
        mock_get_account_tier.side_effect = "SAVINGS"
        mock_get_tiered_parameter_value_based_on_account_tier.side_effect = [Decimal("100")]
        result = minimum_balance_by_tier.validate(
            vault=MagicMock(),
            postings=posting_instructions,
            denomination=DEFAULT_DENOMINATION,
            balances=self.balances(default_committed=Decimal("100")),
        )
        expected_rejection = Rejection(
            message="Transaction amount -1 GBP will result in the account balance falling "
            "below the minimum permitted of 100 GBP.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        self.assertEqual(result, expected_rejection)

    @patch.object(minimum_balance_by_tier.utils, "get_parameter")
    @patch.object(minimum_balance_by_tier.account_tiers, "get_account_tier")
    @patch.object(
        minimum_balance_by_tier.account_tiers, "get_tiered_parameter_value_based_on_account_tier"
    )
    def test_account_tier_minimum_balance_not_exceeded(
        self,
        mock_get_tiered_parameter_value_based_on_account_tier: MagicMock,
        mock_get_account_tier: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # Current balance is 100 so a withdrawal up to 100 should be permitted on a STANDARD account
        posting_instructions = [self.outbound_hard_settlement(amount=Decimal("99"))]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"tiered_minimum_balance_threshold": {"STANDARD": "0", "SAVINGS": "100"}}
        )
        mock_get_account_tier.side_effect = "STANDARD"
        mock_get_tiered_parameter_value_based_on_account_tier.side_effect = [Decimal("0")]
        self.assertIsNone(
            minimum_balance_by_tier.validate(
                vault=MagicMock(),
                postings=posting_instructions,
                denomination=DEFAULT_DENOMINATION,
                balances=self.balances(default_committed=Decimal("100")),
            )
        )

    @patch.object(minimum_balance_by_tier.utils, "get_parameter")
    @patch.object(minimum_balance_by_tier.account_tiers, "get_account_tier")
    @patch.object(
        minimum_balance_by_tier.account_tiers, "get_tiered_parameter_value_based_on_account_tier"
    )
    def test_account_tier_minimum_balance_exceeded_below_zero(
        self,
        mock_get_tiered_parameter_value_based_on_account_tier: MagicMock,
        mock_get_account_tier: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # Current balance is 100 so a withdrawal over 100 should be Rejection on a STANDARD account
        posting_instructions = [self.outbound_hard_settlement(amount=Decimal("101"))]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"tiered_minimum_balance_threshold": {"STANDARD": "0", "SAVINGS": "100"}}
        )
        mock_get_account_tier.side_effect = "STANDARD"
        mock_get_tiered_parameter_value_based_on_account_tier.side_effect = [Decimal("0")]
        result = minimum_balance_by_tier.validate(
            vault=MagicMock(),
            postings=posting_instructions,
            denomination=DEFAULT_DENOMINATION,
            balances=self.balances(default_committed=Decimal("100")),
        )
        expected_rejection = Rejection(
            message="Transaction amount -101 GBP will result in the account balance "
            "falling below the minimum permitted of 0 GBP.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        self.assertEqual(result, expected_rejection)

    @patch.object(minimum_balance_by_tier.utils, "get_parameter")
    @patch.object(minimum_balance_by_tier.account_tiers, "get_account_tier")
    @patch.object(
        minimum_balance_by_tier.account_tiers, "get_tiered_parameter_value_based_on_account_tier"
    )
    def test_account_tier_minimum_balance_exceeded_when_balances_argument_is_not_provided(
        self,
        mock_get_tiered_parameter_value_based_on_account_tier: MagicMock,
        mock_get_account_tier: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # Current balance is 100 so a withdrawal over 100 should be Rejection on a STANDARD account
        posting_instructions = [self.outbound_hard_settlement(amount=Decimal("101"))]
        balances = self.balances(default_committed=Decimal(100))
        test_balance_observation_fetcher_mapping = {
            "live_balances_bof": BalancesObservation(balances=balances)
        }
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"tiered_minimum_balance_threshold": {"STANDARD": "0", "SAVINGS": "100"}}
        )
        mock_get_account_tier.side_effect = "STANDARD"
        mock_get_tiered_parameter_value_based_on_account_tier.side_effect = [Decimal("0")]
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=test_balance_observation_fetcher_mapping
        )
        result = minimum_balance_by_tier.validate(
            vault=mock_vault,
            postings=posting_instructions,
            denomination=DEFAULT_DENOMINATION,
        )
        expected_rejection = Rejection(
            message="Transaction amount -101 GBP will result in the account balance "
            "falling below the minimum permitted of 0 GBP.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        self.assertEqual(result, expected_rejection)

    @patch.object(minimum_balance_by_tier.utils, "get_parameter")
    @patch.object(minimum_balance_by_tier.account_tiers, "get_account_tier")
    @patch.object(
        minimum_balance_by_tier.account_tiers, "get_tiered_parameter_value_based_on_account_tier"
    )
    def test_account_tier_minimum_balance_not_exceeded_when_balances_argument_is_not_provided(
        self,
        mock_get_tiered_parameter_value_based_on_account_tier: MagicMock,
        mock_get_account_tier: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # Current balance is 100 so a withdrawal over 100 should be Rejection on a STANDARD account
        posting_instructions = [self.outbound_hard_settlement(amount=Decimal("50"))]
        balances = self.balances(default_committed=Decimal("100"))
        test_balance_observation_fetcher_mapping = {
            "live_balances_bof": BalancesObservation(balances=balances)
        }
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"tiered_minimum_balance_threshold": {"STANDARD": "0", "SAVINGS": "100"}}
        )
        mock_get_account_tier.side_effect = "STANDARD"
        mock_get_tiered_parameter_value_based_on_account_tier.side_effect = [Decimal("0")]

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=test_balance_observation_fetcher_mapping
        )
        self.assertIsNone(
            minimum_balance_by_tier.validate(
                vault=mock_vault,
                postings=posting_instructions,
                denomination=DEFAULT_DENOMINATION,
            )
        )

    @patch.object(minimum_balance_by_tier.utils, "get_parameter")
    @patch.object(minimum_balance_by_tier.account_tiers, "get_account_tier")
    @patch.object(
        minimum_balance_by_tier.account_tiers, "get_tiered_parameter_value_based_on_account_tier"
    )
    def test_account_tier_minimum_balance_multi_postings_limit_not_exceeded(
        self,
        mock_get_tiered_parameter_value_based_on_account_tier: MagicMock,
        mock_get_account_tier: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # Current balance is 100 so a withdrawal over 100 should be Rejection on a STANDARD account
        posting_instructions = [
            self.inbound_hard_settlement(amount=Decimal("50")),
            self.outbound_hard_settlement(amount=Decimal("50")),
            self.outbound_hard_settlement(amount=Decimal("50")),
            self.outbound_hard_settlement(amount=Decimal("50")),
        ]
        balances = self.balances(default_committed=Decimal("100"))
        test_balance_observation_fetcher_mapping = {
            "live_balances_bof": BalancesObservation(balances=balances)
        }
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"tiered_minimum_balance_threshold": {"STANDARD": "0", "SAVINGS": "100"}}
        )
        mock_get_account_tier.side_effect = "STANDARD"
        mock_get_tiered_parameter_value_based_on_account_tier.side_effect = [Decimal("0")]

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=test_balance_observation_fetcher_mapping
        )
        self.assertIsNone(
            minimum_balance_by_tier.validate(
                vault=mock_vault,
                postings=posting_instructions,
                denomination=DEFAULT_DENOMINATION,
            )
        )

    @patch.object(minimum_balance_by_tier.utils, "get_parameter")
    @patch.object(minimum_balance_by_tier.account_tiers, "get_account_tier")
    @patch.object(
        minimum_balance_by_tier.account_tiers, "get_tiered_parameter_value_based_on_account_tier"
    )
    def test_account_tier_minimum_balance_multi_postings_limit_exceeded(
        self,
        mock_get_tiered_parameter_value_based_on_account_tier: MagicMock,
        mock_get_account_tier: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # Current balance is 100 so a withdrawal over 100 should be Rejection on a STANDARD account
        posting_instructions = [
            self.inbound_hard_settlement(amount=Decimal("50")),
            self.outbound_hard_settlement(amount=Decimal("50")),
            self.outbound_hard_settlement(amount=Decimal("50")),
            self.outbound_hard_settlement(amount=Decimal("50.01")),
        ]
        balances = self.balances(default_committed=Decimal("100"))
        test_balance_observation_fetcher_mapping = {
            "live_balances_bof": BalancesObservation(balances=balances)
        }
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"tiered_minimum_balance_threshold": {"STANDARD": "0", "SAVINGS": "100"}}
        )
        mock_get_account_tier.side_effect = "STANDARD"
        mock_get_tiered_parameter_value_based_on_account_tier.side_effect = [Decimal("0")]

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=test_balance_observation_fetcher_mapping
        )
        result = minimum_balance_by_tier.validate(
            vault=mock_vault,
            postings=posting_instructions,
            denomination=DEFAULT_DENOMINATION,
        )
        expected_rejection = Rejection(
            message="Transaction amount -100.01 GBP will result in the account balance "
            "falling below the minimum permitted of 0 GBP.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        self.assertEqual(result, expected_rejection)
