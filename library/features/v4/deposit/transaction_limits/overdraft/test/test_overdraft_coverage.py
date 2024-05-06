# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# features
import library.features.v4.deposit.transaction_limits.overdraft.overdraft_coverage as overdraft_coverage  # noqa: E501
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.deposit.transaction_limits.test.test_common_transaction_limit import (  # noqa: E501
    CommonTransactionLimitTest,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DENOMINATION
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    Rejection,
    RejectionReason,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
)

EXCLUDED_TYPE = "excluded_transaction_type"
excluded_type_instruction_details = {"type": EXCLUDED_TYPE}


class TestOverdraftLimit(CommonTransactionLimitTest):
    def setUp(self) -> None:

        # get parameter
        patch_get_parameter = patch.object(overdraft_coverage.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "overdraft_coverage_opted_in": False,
                "excluded_overdraft_coverage_transaction_types": [EXCLUDED_TYPE],
                overdraft_coverage.overdraft_limit.PARAM_ARRANGED_OVERDRAFT_AMOUNT: Decimal("10"),
                overdraft_coverage.overdraft_limit.PARAM_UNARRANGED_OVERDRAFT_AMOUNT: Decimal("0"),
            }
        )

        patch_get_available_balances = patch.object(
            overdraft_coverage.utils, "get_available_balance"
        )
        self.mock_get_available_balance = patch_get_available_balances.start()
        # side_effect of the above instance mock is expected to be set in each test as required

        self.expected_rejection_empty_posting_type = Rejection(
            message="posting_type='' exceeds the total available balance of the account.",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )
        self.expected_rejection_excluded_posting_type = Rejection(
            message=(
                f"posting_type='{EXCLUDED_TYPE}' exceeds the total available balance of the "
                "account. This transaction is an excluded transaction type which requires "
                "overdraft coverage opt-in to utilise the overdraft limit."
            ),
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )
        self.addCleanup(patch.stopall)
        return super().setUp()

    @patch.object(overdraft_coverage.overdraft_limit, "validate")
    def test_validate_returns_overdraft_limit_if_opted_in(
        self, mock_overdraft_limit_validate: MagicMock
    ):
        mock_overdraft_limit_validate.return_value = sentinel.overdraft_limit
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "overdraft_coverage_opted_in": True,
            }
        )
        result = overdraft_coverage.validate(
            vault=sentinel.vault,
            postings=sentinel.posting_instructions,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )
        self.assertEqual(result, sentinel.overdraft_limit)
        mock_overdraft_limit_validate.assert_called_once_with(
            vault=sentinel.vault,
            postings=sentinel.posting_instructions,
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )

    @patch.object(overdraft_coverage.overdraft_limit, "validate")
    def test_validate_returns_overdraft_limit_if_opted_in_optional_args_not_provided(
        self, mock_overdraft_limit_validate: MagicMock
    ):
        mock_overdraft_limit_validate.return_value = sentinel.overdraft_limit
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "overdraft_coverage_opted_in": True,
                overdraft_coverage.common_parameters.PARAM_DENOMINATION: sentinel.denomination,
            }
        )
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                overdraft_coverage.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "live_observation"
                )
            }
        )
        result = overdraft_coverage.validate(
            vault=mock_vault,
            postings=sentinel.posting_instructions,
        )
        self.assertEqual(result, sentinel.overdraft_limit)
        mock_overdraft_limit_validate.assert_called_once_with(
            vault=mock_vault,
            postings=sentinel.posting_instructions,
            denomination=sentinel.denomination,
            balances=sentinel.balances_live_observation,
        )

    def test_validate_returns_none_for_deposits(self):
        # available_balance, OHS posting balance
        self.mock_get_available_balance.side_effect = [Decimal("10"), Decimal("10")]
        posting_instructions = [
            self.inbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("10"),
                instruction_details=excluded_type_instruction_details,
            ),
        ]
        result = overdraft_coverage.validate(
            vault=sentinel.vault,
            postings=posting_instructions,
            balances=sentinel.balances,
            denomination=DEFAULT_DENOMINATION,
        )
        self.assertIsNone(result)

    def test_overdraft_coverage_rejects_excluded_withdrawal_that_exceeds_available_balance(self):

        # available_balance, OHS posting balance
        self.mock_get_available_balance.side_effect = [Decimal("10"), Decimal("-11")]

        posting_instructions = [
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("11"),
                instruction_details=excluded_type_instruction_details,
            )
        ]

        result = overdraft_coverage.validate(
            vault=sentinel,
            postings=posting_instructions,
            balances=sentinel.balances,
            denomination=DEFAULT_DENOMINATION,
        )
        self.assertEqual(result, self.expected_rejection_excluded_posting_type)

    def test_overdraft_coverage_rejects_non_excluded_withdrawal_that_exceeds_available_balance(
        self,
    ):
        # available_balance, OHS posting balance
        self.mock_get_available_balance.side_effect = [Decimal("10"), Decimal("-21")]
        posting_instructions = [
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("21"),
            ),
        ]

        result = overdraft_coverage.validate(
            vault=sentinel,
            postings=posting_instructions,
            balances=sentinel.balances,
            denomination=DEFAULT_DENOMINATION,
        )
        self.assertEqual(result, self.expected_rejection_empty_posting_type)

    def test_validate_returns_rejection_if_local_negative_net_positive(self):
        # available_balance, OHS posting balance
        self.mock_get_available_balance.side_effect = [Decimal("10"), Decimal("-21")]
        posting_instructions = [
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("11"),
                instruction_details=excluded_type_instruction_details,
            ),
            self.inbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("100"),
                instruction_details=excluded_type_instruction_details,
            ),
        ]

        result = overdraft_coverage.validate(
            vault=sentinel.vault,
            postings=posting_instructions,
            balances=sentinel.balances,
            denomination=DEFAULT_DENOMINATION,
        )
        self.assertEqual(result, self.expected_rejection_excluded_posting_type)

    def test_validate_returns_none_excluded_does_not_utilise_overdraft_and_allowed_within_limit(
        self,
    ):
        # available_balance, excluded txn posting balance, non-excluded txn posting balance
        self.mock_get_available_balance.side_effect = [Decimal("10"), Decimal("-2"), Decimal("-10")]
        posting_instructions = [
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("2"),
                instruction_details=excluded_type_instruction_details,
            ),
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("10"),
            ),
        ]

        result = overdraft_coverage.validate(
            vault=sentinel.vault,
            postings=posting_instructions,
            balances=sentinel.balances,
            denomination=DEFAULT_DENOMINATION,
        )
        self.assertIsNone(result)

    def test_validate_returns_rejection_allowed_uses_non_overdraft_balance(
        self,
    ):
        # available_balance, non-excluded txn posting balance, excluded txn posting balance
        self.mock_get_available_balance.side_effect = [Decimal("10"), Decimal("-9"), Decimal("-2")]
        posting_instructions = [
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("9"),
            ),
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("2"),
                instruction_details=excluded_type_instruction_details,
            ),
        ]

        result = overdraft_coverage.validate(
            vault=sentinel.vault,
            postings=posting_instructions,
            balances=sentinel.balances,
            denomination=DEFAULT_DENOMINATION,
        )
        self.assertEqual(result, self.expected_rejection_excluded_posting_type)

    def test_validate_returns_rejection_excluded_does_not_utilise_overdraft_allowed_outside_limit(
        self,
    ):
        # available_balance, excluded txn posting balance, non-excluded txn posting balance
        self.mock_get_available_balance.side_effect = [Decimal("10"), Decimal("-9"), Decimal("-13")]
        posting_instructions = [
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("9"),
                instruction_details=excluded_type_instruction_details,
            ),
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("13"),
            ),
        ]

        result = overdraft_coverage.validate(
            vault=sentinel.vault,
            postings=posting_instructions,
            balances=sentinel.balances,
            denomination=DEFAULT_DENOMINATION,
        )
        self.assertEqual(result, self.expected_rejection_empty_posting_type)

    def test_validate_returns_rejection_allowed_within_limit_excluded_exceeds_limit(
        self,
    ):
        # available_balance, excluded txn posting balance, non-excluded txn posting balance
        self.mock_get_available_balance.side_effect = [Decimal("10"), Decimal("-5"), Decimal("-6")]
        posting_instructions = [
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("5"),
            ),
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("6"),
                instruction_details=excluded_type_instruction_details,
            ),
        ]

        result = overdraft_coverage.validate(
            vault=sentinel.vault,
            postings=posting_instructions,
            balances=sentinel.balances,
            denomination=DEFAULT_DENOMINATION,
        )
        self.assertEqual(result, self.expected_rejection_excluded_posting_type)
