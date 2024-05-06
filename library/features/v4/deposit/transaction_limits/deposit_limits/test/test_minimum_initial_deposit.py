# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.deposit.transaction_limits.deposit_limits import minimum_initial_deposit
from library.features.v4.deposit.transaction_limits.test.test_common_transaction_limit import (
    CommonTransactionLimitTest,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DENOMINATION
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    BalancesObservation,
    Rejection,
    RejectionReason,
)


class TestMinimumInitialDeposit(CommonTransactionLimitTest):
    @patch.object(minimum_initial_deposit.utils, "get_parameter")
    def test_minimum_initial_deposit_ignore_withdrawal(self, mock_get_parameter: MagicMock):
        postings = [
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("1000"))
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"minimum_initial_deposit": Decimal("20")}
        )
        self.assertIsNone(
            minimum_initial_deposit.validate(
                vault=MagicMock(),
                postings=postings,
                balances=self.balances(default_committed=Decimal("1")),
                denomination=DEFAULT_DENOMINATION,
            )
        )

    @patch.object(minimum_initial_deposit.utils, "get_parameter")
    def test_minimum_initial_deposit_with_single_posting_not_met(
        self, mock_get_parameter: MagicMock
    ):
        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("19"))
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"minimum_initial_deposit": Decimal("20")}
        )
        result = minimum_initial_deposit.validate(
            vault=MagicMock(),
            postings=postings,
            balances=self.balances(),
            denomination=DEFAULT_DENOMINATION,
        )
        expected_rejection = Rejection(
            message=f"Transaction amount 19.00 {DEFAULT_DENOMINATION} is less than the minimum "
            f"initial deposit amount 20.00 {DEFAULT_DENOMINATION}.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        self.assertEqual(result, expected_rejection)

    @patch.object(minimum_initial_deposit.utils, "get_parameter")
    def test_minimum_initial_deposit_with_single_posting_met(self, mock_get_parameter: MagicMock):
        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("20"))
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"minimum_initial_deposit": Decimal("20")}
        )
        self.assertIsNone(
            minimum_initial_deposit.validate(
                vault=MagicMock(),
                postings=postings,
                balances=self.balances(),
                denomination=DEFAULT_DENOMINATION,
            )
        )

    @patch.object(minimum_initial_deposit.utils, "get_parameter")
    def test_minimum_initial_deposit_not_met_but_balance_exists(
        self, mock_get_parameter: MagicMock
    ):
        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("1"))
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"minimum_initial_deposit": Decimal("20")}
        )
        self.assertIsNone(
            minimum_initial_deposit.validate(
                vault=MagicMock(),
                postings=postings,
                balances=self.balances(default_committed=Decimal("19")),
                denomination=DEFAULT_DENOMINATION,
            )
        )

    @patch.object(minimum_initial_deposit.utils, "get_parameter")
    def test_minimum_initial_deposit_not_met_when_balance_argument_is_not_provided(
        self, mock_get_parameter: MagicMock
    ):
        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("1"))
        ]
        balances = self.balances()
        test_balance_observation_fetcher_mapping = {
            "live_balances_bof": BalancesObservation(balances=balances)
        }
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"minimum_initial_deposit": Decimal("20")}
        )
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=test_balance_observation_fetcher_mapping,
        )
        result = minimum_initial_deposit.validate(
            vault=mock_vault, postings=postings, denomination=DEFAULT_DENOMINATION
        )
        expected_rejection = Rejection(
            message=f"Transaction amount 1.00 {DEFAULT_DENOMINATION} is less than the minimum "
            f"initial deposit amount 20.00 {DEFAULT_DENOMINATION}.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        self.assertEqual(result, expected_rejection)

    @patch.object(minimum_initial_deposit.utils, "get_parameter")
    def test_minimum_initial_deposit_is_over_limit_when_balance_argument_is_not_provided(
        self, mock_get_parameter: MagicMock
    ):
        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("25"))
        ]
        balances = self.balances()
        test_balance_observation_fetcher_mapping = {
            "live_balances_bof": BalancesObservation(balances=balances)
        }
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"minimum_initial_deposit": Decimal("20")}
        )
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=test_balance_observation_fetcher_mapping,
        )
        self.assertIsNone(
            minimum_initial_deposit.validate(
                vault=mock_vault, postings=postings, denomination=DEFAULT_DENOMINATION
            )
        )

    @patch.object(minimum_initial_deposit.utils, "get_parameter")
    def test_no_rejection_when_net_affect_of_multiple_postings_is_equal_to_the_min_initial_deposit(
        self, mock_get_parameter: MagicMock
    ):
        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("10")),
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("5")),
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("5")),
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"minimum_initial_deposit": Decimal("20")}
        )
        self.assertIsNone(
            minimum_initial_deposit.validate(
                vault=sentinel.vault,
                postings=postings,
                balances=self.balances(),
                denomination=DEFAULT_DENOMINATION,
            )
        )

    @patch.object(minimum_initial_deposit.utils, "get_parameter")
    def test_no_rejection_when_net_affect_of_multiple_postings_is_above_the_min_initial_deposit(
        self, mock_get_parameter: MagicMock
    ):
        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("11")),
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("5")),
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("5")),
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"minimum_initial_deposit": Decimal("20")}
        )
        self.assertIsNone(
            minimum_initial_deposit.validate(
                vault=sentinel.vault,
                postings=postings,
                balances=self.balances(),
                denomination=DEFAULT_DENOMINATION,
            )
        )

    @patch.object(minimum_initial_deposit.utils, "get_parameter")
    def test_rejection_raised_when_net_affect_of_multiple_postings_is_below_the_min_initial_deposit(
        self, mock_get_parameter: MagicMock
    ):
        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("20")),
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("20")),
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("5")),
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"minimum_initial_deposit": Decimal("20")}
        )
        result = minimum_initial_deposit.validate(
            vault=sentinel.vault,
            postings=postings,
            balances=self.balances(),
            denomination=DEFAULT_DENOMINATION,
        )
        expected_rejection = Rejection(
            message="Transaction amount 5.00 GBP is less than the "
            "minimum initial deposit amount 20.00 GBP.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        self.assertEqual(result, expected_rejection)
