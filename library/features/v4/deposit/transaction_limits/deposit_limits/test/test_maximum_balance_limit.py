# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.deposit.transaction_limits.deposit_limits import maximum_balance_limit
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


class TestMaximumBalanceLimit(CommonTransactionLimitTest):
    @patch.object(maximum_balance_limit.utils, "get_parameter")
    def test_maximum_balance_limit_ignore_withdrawal(self, mock_get_parameter: MagicMock):
        posting_instructions = [
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("1000"))
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_balance": Decimal("100")}
        )
        self.assertIsNone(
            maximum_balance_limit.validate(
                vault=MagicMock(),
                postings=posting_instructions,
                balances=self.balances(),
                denomination=DEFAULT_DENOMINATION,
            )
        )

    @patch.object(maximum_balance_limit.utils, "get_parameter")
    def test_maximum_balance_limit_postings_total_is_under_the_limit(
        self, mock_get_parameter: MagicMock
    ):
        posting_instructions = [
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION, amount=Decimal("1000")
            ),
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("500")),
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("500")),
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("99")),
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_balance": Decimal("100")}
        )
        self.assertIsNone(
            maximum_balance_limit.validate(
                vault=MagicMock(),
                postings=posting_instructions,
                balances=self.balances(),
                denomination=DEFAULT_DENOMINATION,
            )
        )

    @patch.object(maximum_balance_limit.utils, "get_parameter")
    def test_maximum_balance_limit_postings_total_is_over_the_limit(
        self, mock_get_parameter: MagicMock
    ):
        posting_instructions = [
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION, amount=Decimal("1000")
            ),
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("500")),
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("500")),
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("101")),
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_balance": Decimal("100")}
        )
        result = maximum_balance_limit.validate(
            vault=MagicMock(),
            postings=posting_instructions,
            balances=self.balances(),
            denomination=DEFAULT_DENOMINATION,
        )
        expected_rejection = Rejection(
            message=f"Posting would exceed maximum permitted balance 100 {DEFAULT_DENOMINATION}.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        self.assertEqual(result, expected_rejection)

    @patch.object(maximum_balance_limit.utils, "get_parameter")
    def test_maximum_balance_limit_exceeded(self, mock_get_parameter: MagicMock):
        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("101"))
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_balance": Decimal("100")}
        )
        expected_rejection = Rejection(
            message=f"Posting would exceed maximum permitted balance 100 {DEFAULT_DENOMINATION}.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        result = maximum_balance_limit.validate(
            vault=MagicMock(),
            postings=postings,
            balances=self.balances(),
            denomination=DEFAULT_DENOMINATION,
        )
        self.assertEqual(result, expected_rejection)

    @patch.object(maximum_balance_limit.utils, "get_parameter")
    def test_maximum_balance_limit_not_exceeded(self, mock_get_parameter: MagicMock):
        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("99"))
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_balance": Decimal("100")}
        )
        self.assertIsNone(
            maximum_balance_limit.validate(
                vault=MagicMock(),
                postings=postings,
                balances=self.balances(),
                denomination=DEFAULT_DENOMINATION,
            )
        )

    @patch.object(maximum_balance_limit.utils, "get_parameter")
    def test_maximum_balance_limit_exceeded_already_over(self, mock_get_parameter: MagicMock):
        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("1"))
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_balance": Decimal("100")}
        )
        result = maximum_balance_limit.validate(
            vault=MagicMock(),
            postings=postings,
            balances=self.balances(default_committed=Decimal("100")),
            denomination=DEFAULT_DENOMINATION,
        )
        expected_rejection = Rejection(
            message=f"Posting would exceed maximum permitted balance 100 {DEFAULT_DENOMINATION}.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        self.assertEqual(result, expected_rejection)

    @patch.object(maximum_balance_limit.utils, "get_parameter")
    def test_maximum_balance_limit_ignore_withdrawals_when_balances_argument_not_provided(
        self, mock_get_parameter: MagicMock
    ):
        posting_instructions = [
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("1000"))
        ]
        balances = self.balances(default_committed=Decimal("99.99"))
        test_balance_observation_fetcher_mapping = {
            "live_balances_bof": BalancesObservation(balances=balances)
        }
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_balance": Decimal("100")}
        )
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=test_balance_observation_fetcher_mapping,
        )
        self.assertIsNone(
            maximum_balance_limit.validate(
                vault=mock_vault,
                postings=posting_instructions,
                denomination=DEFAULT_DENOMINATION,
            )
        )

    @patch.object(maximum_balance_limit.utils, "get_parameter")
    def test_maximum_balance_limit_exceeded_when_balances_argument_not_provided(
        self, mock_get_parameter: MagicMock
    ):
        posting_instructions = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("0.01"))
        ]
        balances = self.balances(default_committed=Decimal("100"))
        test_balance_observation_fetcher_mapping = {
            "live_balances_bof": BalancesObservation(balances=balances)
        }
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_balance": Decimal("100")}
        )
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=test_balance_observation_fetcher_mapping,
        )
        result = maximum_balance_limit.validate(
            vault=mock_vault,
            postings=posting_instructions,
            denomination=DEFAULT_DENOMINATION,
        )
        expected_rejection = Rejection(
            message=f"Posting would exceed maximum permitted balance 100 {DEFAULT_DENOMINATION}.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        self.assertEqual(result, expected_rejection)
