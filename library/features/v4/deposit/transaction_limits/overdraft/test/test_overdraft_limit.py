# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.deposit.transaction_limits.overdraft import overdraft_limit
from library.features.v4.deposit.transaction_limits.test.test_common_transaction_limit import (  # noqa: E501
    CommonTransactionLimitTest,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DENOMINATION
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    BalancesObservation,
    Rejection,
    RejectionReason,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
)


@patch.object(overdraft_limit.utils, "get_parameter")
class TestOverdraftLimitValidate(CommonTransactionLimitTest):
    def test_overdraft_limit_ignore_deposit(self, mock_get_parameter: MagicMock):
        posting_instructions = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("1000"))
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "arranged_overdraft_amount": Decimal("0"),
                "unarranged_overdraft_amount": Decimal("0"),
            }
        )
        self.assertIsNone(
            overdraft_limit.validate(
                vault=sentinel,
                postings=posting_instructions,
                balances=self.balances(default_committed=Decimal("1")),
                denomination=DEFAULT_DENOMINATION,
            )
        )

    def test_no_overdraft_set_accept_posting_balance_above_0(self, mock_get_parameter: MagicMock):
        posting_instructions = [
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("99"))
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "arranged_overdraft_amount": Decimal("0"),
                "unarranged_overdraft_amount": Decimal("0"),
            }
        )
        self.assertIsNone(
            overdraft_limit.validate(
                vault=sentinel,
                postings=posting_instructions,
                denomination=DEFAULT_DENOMINATION,
                balances=self.balances(default_committed=Decimal("100")),
            )
        )

    def test_no_overdraft_set_accept_posting_balance_to_0(self, mock_get_parameter: MagicMock):
        posting_instructions = [
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("100"))
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "arranged_overdraft_amount": Decimal("0"),
                "unarranged_overdraft_amount": Decimal("0"),
            }
        )
        self.assertIsNone(
            overdraft_limit.validate(
                vault=sentinel,
                postings=posting_instructions,
                denomination=DEFAULT_DENOMINATION,
                balances=self.balances(default_committed=Decimal("100")),
            )
        )

    def test_no_overdraft_set_reject_posting_taking_balance_below_0(
        self, mock_get_parameter: MagicMock
    ):
        posting_instructions = [
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("201"))
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "arranged_overdraft_amount": Decimal("0"),
                "unarranged_overdraft_amount": Decimal("0"),
            }
        )
        result = overdraft_limit.validate(
            vault=sentinel,
            postings=posting_instructions,
            denomination=DEFAULT_DENOMINATION,
            balances=self.balances(default_committed=Decimal("100")),
        )
        expected_rejection = Rejection(
            message="Postings total GBP -201, which exceeds the available balance of GBP 100.",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )
        self.assertEqual(result, expected_rejection)

    def test_arranged_overdraft_set_accept_posting_taking_balance_within_overdraft(
        self, mock_get_parameter: MagicMock
    ):
        posting_instructions = [
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("150"))
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "arranged_overdraft_amount": Decimal("100"),
                "unarranged_overdraft_amount": Decimal("0"),
            }
        )
        self.assertIsNone(
            overdraft_limit.validate(
                vault=sentinel,
                postings=posting_instructions,
                denomination=DEFAULT_DENOMINATION,
                balances=self.balances(default_committed=Decimal("100")),
            )
        )

    def test_unarranged_overdraft_set_accept_posting_taking_balance_within_overdraft(
        self, mock_get_parameter: MagicMock
    ):
        posting_instructions = [
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("175"))
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "arranged_overdraft_amount": Decimal("0"),
                "unarranged_overdraft_amount": Decimal("100"),
            }
        )
        self.assertIsNone(
            overdraft_limit.validate(
                vault=sentinel,
                postings=posting_instructions,
                denomination=DEFAULT_DENOMINATION,
                balances=self.balances(default_committed=Decimal("100")),
            )
        )

    def test_no_overdraft_set_accept_posting_net_batch_accepted(
        self, mock_get_parameter: MagicMock
    ):
        posting_instructions = [
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("150")),
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("60")),
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "arranged_overdraft_amount": Decimal("0"),
                "unarranged_overdraft_amount": Decimal("0"),
            }
        )
        self.assertIsNone(
            overdraft_limit.validate(
                vault=sentinel,
                postings=posting_instructions,
                denomination=DEFAULT_DENOMINATION,
                balances=self.balances(default_committed=Decimal("100")),
            )
        )

    def test_no_overdraft_set_accept_posting_net_batch_rejected(
        self, mock_get_parameter: MagicMock
    ):
        posting_instructions = [
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("150")),
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("40")),
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "arranged_overdraft_amount": Decimal("0"),
                "unarranged_overdraft_amount": Decimal("0"),
            }
        )
        result = overdraft_limit.validate(
            vault=sentinel,
            postings=posting_instructions,
            denomination=DEFAULT_DENOMINATION,
            balances=self.balances(default_committed=Decimal("100")),
        )
        expected_rejection = Rejection(
            message="Postings total GBP -110, which exceeds the available balance of GBP 100.",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )
        self.assertEqual(result, expected_rejection)

    def test_both_overdrafts_set_accept_posting_net_batch_balance_argument_not_provided(
        self, mock_get_parameter: MagicMock
    ):
        posting_instructions = [
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("150")),
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("75")),
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("25")),
        ]
        balances = self.balances(default_committed=Decimal("100"))
        test_balance_observation_fetcher_mapping = {
            "live_balances_bof": BalancesObservation(balances=balances)
        }
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "arranged_overdraft_amount": Decimal("50"),
                "unarranged_overdraft_amount": Decimal("50"),
            }
        )
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=test_balance_observation_fetcher_mapping,
        )
        self.assertIsNone(
            overdraft_limit.validate(
                vault=mock_vault,
                postings=posting_instructions,
                denomination=DEFAULT_DENOMINATION,
            )
        )

    def test_overdraft_limit_ignore_deposit_balance_already_negative(
        self, mock_get_parameter: MagicMock
    ):
        posting_instructions = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("1000")),
            self.inbound_auth(denomination=DEFAULT_DENOMINATION, amount=Decimal("1000")),
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "arranged_overdraft_amount": Decimal("0"),
                "unarranged_overdraft_amount": Decimal("0"),
            }
        )
        self.assertIsNone(
            overdraft_limit.validate(
                vault=sentinel,
                postings=posting_instructions,
                balances=self.balances(default_committed=Decimal("-500")),
                denomination=DEFAULT_DENOMINATION,
            )
        )

    def test_overdraft_limit_accept_posting_balance_already_negative_but_within_limit(
        self, mock_get_parameter: MagicMock
    ):
        posting_instructions = [
            self.outbound_auth(denomination=DEFAULT_DENOMINATION, amount=Decimal("250"))
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "arranged_overdraft_amount": Decimal("200"),
                "unarranged_overdraft_amount": Decimal("100"),
            }
        )
        self.assertIsNone(
            overdraft_limit.validate(
                vault=sentinel,
                postings=posting_instructions,
                balances=self.balances(default_committed=Decimal("-50")),
                denomination=DEFAULT_DENOMINATION,
            )
        )

    def test_overdraft_limit_rejects_posting_balance_already_negative_and_goes_over_limit(
        self, mock_get_parameter: MagicMock
    ):
        posting_instructions = [
            self.outbound_auth(denomination=DEFAULT_DENOMINATION, amount=Decimal("200")),
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("200")),
            self.inbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION, amount=Decimal("49.99")
            ),
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "arranged_overdraft_amount": Decimal("200"),
                "unarranged_overdraft_amount": Decimal("200"),
            }
        )
        result = overdraft_limit.validate(
            vault=sentinel,
            postings=posting_instructions,
            balances=self.balances(default_committed=Decimal("-50")),
            denomination=DEFAULT_DENOMINATION,
        )
        expected_rejection = Rejection(
            message="Postings total GBP -350.01, which exceeds the available balance of GBP 350.",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )
        self.assertEqual(result, expected_rejection)

    def test_overdraft_limit_rejects_posting_different_denomination_when_no_limit_set(
        self, mock_get_parameter: MagicMock
    ):
        posting_instructions = [
            self.outbound_hard_settlement(denomination="USD", amount=Decimal("99")),
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "arranged_overdraft_amount": Decimal("0"),
                "unarranged_overdraft_amount": Decimal("0"),
            }
        )
        result = overdraft_limit.validate(
            vault=sentinel,
            postings=posting_instructions,
            balances=self.balances(default_committed=Decimal("100")),
            denomination="USD",
        )
        expected_rejection = Rejection(
            message="Postings total USD -99, which exceeds the available balance of USD 0.",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )
        self.assertEqual(result, expected_rejection)

    def test_overdraft_limit_accepts_posting_different_denomination_when_under_limit(
        self, mock_get_parameter: MagicMock
    ):
        posting_instructions = [
            self.outbound_hard_settlement(denomination="USD", amount=Decimal("99")),
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "arranged_overdraft_amount": Decimal("100"),
                "unarranged_overdraft_amount": Decimal("0"),
            }
        )
        self.assertIsNone(
            overdraft_limit.validate(
                vault=sentinel,
                postings=posting_instructions,
                balances=self.balances(default_committed=Decimal("100")),
                denomination="USD",
            )
        )

    def test_overdraft_limit_rejects_posting_different_denomination_when_over_limit(
        self, mock_get_parameter: MagicMock
    ):
        posting_instructions = [
            self.outbound_hard_settlement(denomination="USD", amount=Decimal("100.01")),
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "arranged_overdraft_amount": Decimal("0"),
                "unarranged_overdraft_amount": Decimal("100"),
            }
        )
        result = overdraft_limit.validate(
            vault=sentinel,
            postings=posting_instructions,
            balances=self.balances(default_committed=Decimal("100")),
            denomination="USD",
        )
        expected_rejection = Rejection(
            message="Postings total USD -100.01, which exceeds the available balance of USD 100.",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )
        self.assertEqual(result, expected_rejection)


@patch.object(overdraft_limit.utils, "get_available_balance")
@patch.object(overdraft_limit.utils, "get_parameter")
class TestOverdraftAvailableBalance(CommonTransactionLimitTest):
    def test_get_overdraft_available_balance_args_provided(
        self, mock_get_parameter: MagicMock, mock_get_available_balance: MagicMock
    ):
        mock_get_available_balance.return_value = Decimal("10")
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "arranged_overdraft_amount": Decimal("1"),
                "unarranged_overdraft_amount": Decimal("2"),
            }
        )
        result = overdraft_limit.get_overdraft_available_balance(
            vault=sentinel.vault, balances=sentinel.balances, denomination=sentinel.denomination
        )
        self.assertEqual(result, Decimal("13"))
        mock_get_available_balance.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    vault=sentinel.vault,
                    name="arranged_overdraft_amount",
                    is_optional=True,
                    default_value=Decimal("0"),
                ),
                call(
                    vault=sentinel.vault,
                    name="unarranged_overdraft_amount",
                    is_optional=True,
                    default_value=Decimal("0"),
                ),
            ]
        )
        self.assertEqual(mock_get_parameter.call_count, 2)

    def test_get_overdraft_available_balance_optional_args_not_provided(
        self, mock_get_parameter: MagicMock, mock_get_available_balance: MagicMock
    ):
        mock_get_available_balance.return_value = Decimal("10")
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "arranged_overdraft_amount": Decimal("1"),
                "unarranged_overdraft_amount": Decimal("2"),
                "denomination": "GBP",
            }
        )
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                "live_balances_bof": SentinelBalancesObservation("live")
            }
        )
        result = overdraft_limit.get_overdraft_available_balance(vault=mock_vault)
        self.assertEqual(result, Decimal("13"))
        mock_get_available_balance.assert_called_once_with(
            balances=sentinel.balances_live, denomination="GBP"
        )
        mock_get_parameter.assert_has_calls(
            calls=[
                call(vault=mock_vault, name="denomination", at_datetime=None),
                call(
                    vault=mock_vault,
                    name="arranged_overdraft_amount",
                    is_optional=True,
                    default_value=Decimal("0"),
                ),
                call(
                    vault=mock_vault,
                    name="unarranged_overdraft_amount",
                    is_optional=True,
                    default_value=Decimal("0"),
                ),
            ]
        )
        self.assertEqual(mock_get_parameter.call_count, 3)
