# standard libs
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.deposit.transaction_limits.test.test_common_transaction_limit import (
    CUT_OFF_DATE,
    CommonTransactionLimitTest,
)
from library.features.v4.deposit.transaction_limits.withdrawal_limits import (
    maximum_daily_withdrawal,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DENOMINATION
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PrePostingHookArguments,
    Rejection,
    RejectionReason,
)


@patch.object(maximum_daily_withdrawal.client_transaction_utils, "sum_client_transactions")
@patch.object(maximum_daily_withdrawal.utils, "get_parameter")
class TestMaximumDailyDepositLimit(CommonTransactionLimitTest):
    def test_maximum_daily_withdrawal_ignore_deposit(
        self, mock_get_parameter: MagicMock, mock_sum_client_transactions: MagicMock
    ):
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)

        # mocks
        mock_get_parameter.return_value = {}
        mock_sum_client_transactions.side_effect = [(Decimal("501"), Decimal("0"))]

        # call to function
        result = maximum_daily_withdrawal.validate(
            vault=sentinel.vault,
            hook_arguments=PrePostingHookArguments(
                effective_datetime=value_datetime,
                posting_instructions=sentinel.posting_instructions,
                client_transactions=sentinel.client_transactions,
            ),
            denomination=sentinel.denomination,
            effective_date_client_transactions=sentinel.effective_date_transactions,
        )

        # assertions
        self.assertIsNone(result)
        mock_sum_client_transactions.assert_called_once_with(
            cutoff_datetime=value_datetime,
            client_transactions=sentinel.client_transactions,
            denomination=sentinel.denomination,
        )
        mock_get_parameter.assert_not_called()

    def test_maximum_daily_withdrawal_exceeded_when_limit_has_not_been_spent(
        self, mock_get_parameter: MagicMock, mock_sum_client_transactions: MagicMock
    ):
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)

        expected_rejection = Rejection(
            message=f"Transactions would cause the maximum daily withdrawal limit of "
            f"500 {DEFAULT_DENOMINATION} to be exceeded.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        # mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_daily_withdrawal": Decimal("500")}
        )
        mock_sum_client_transactions.side_effect = [
            (Decimal("0"), Decimal("501")),
            (Decimal("0"), Decimal("0")),
        ]

        # call to function
        result = maximum_daily_withdrawal.validate(
            vault=sentinel.vault,
            hook_arguments=PrePostingHookArguments(
                effective_datetime=value_datetime,
                posting_instructions=sentinel.posting_instructions,
                client_transactions=sentinel.client_transactions,
            ),
            denomination=DEFAULT_DENOMINATION,
            effective_date_client_transactions=sentinel.effective_date_transactions,
        )

        # assertions
        self.assertEqual(result, expected_rejection)
        mock_sum_client_transactions.assert_has_calls(
            calls=[
                call(
                    cutoff_datetime=value_datetime,
                    client_transactions=sentinel.client_transactions,
                    denomination=DEFAULT_DENOMINATION,
                ),
                call(
                    cutoff_datetime=CUT_OFF_DATE,
                    client_transactions=sentinel.effective_date_transactions,
                    denomination=DEFAULT_DENOMINATION,
                ),
            ]
        )
        mock_get_parameter.assert_called_once_with(
            vault=sentinel.vault, name="maximum_daily_withdrawal"
        )

    def test_maximum_daily_withdrawal_met(
        self, mock_get_parameter: MagicMock, mock_sum_client_transactions: MagicMock
    ):
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)

        # mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_daily_withdrawal": Decimal("500")}
        )
        mock_sum_client_transactions.side_effect = [
            (Decimal("0"), Decimal("300")),
            (Decimal("0"), Decimal("200")),
        ]

        # call to function
        result = maximum_daily_withdrawal.validate(
            vault=sentinel.vault,
            hook_arguments=PrePostingHookArguments(
                effective_datetime=value_datetime,
                posting_instructions=sentinel.posting_instructions,
                client_transactions=sentinel.client_transactions,
            ),
            denomination=sentinel.denomination,
            effective_date_client_transactions=sentinel.effective_date_transactions,
        )

        # assertions
        self.assertIsNone(result)

    def test_maximum_daily_withdrawal_not_exceeded(
        self, mock_get_parameter: MagicMock, mock_sum_client_transactions: MagicMock
    ):
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)

        # mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_daily_withdrawal": Decimal("500")}
        )
        mock_sum_client_transactions.side_effect = [
            (Decimal("0"), Decimal("100")),
            (Decimal("0"), Decimal("200")),
        ]

        # call to function
        result = maximum_daily_withdrawal.validate(
            vault=sentinel.vault,
            hook_arguments=PrePostingHookArguments(
                effective_datetime=value_datetime,
                posting_instructions=sentinel.posting_instructions,
                client_transactions=sentinel.client_transactions,
            ),
            denomination=sentinel.denomination,
            effective_date_client_transactions=sentinel.effective_date_transactions,
        )

        # assertions
        self.assertIsNone(result)

    def test_maximum_daily_withdrawal_not_exceeded_transactions_not_provided(
        self, mock_get_parameter: MagicMock, mock_sum_client_transactions: MagicMock
    ):
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)

        # mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_daily_withdrawal": Decimal("500")}
        )
        mock_sum_client_transactions.side_effect = [
            (Decimal("0"), Decimal("100")),
            (Decimal("0"), Decimal("200")),
        ]

        mock_vault = self.create_mock(
            client_transactions_mapping={
                "EFFECTIVE_DATE_POSTINGS_FETCHER": sentinel.effective_date_transactions
            }
        )

        # call to function
        result = maximum_daily_withdrawal.validate(
            vault=mock_vault,
            hook_arguments=PrePostingHookArguments(
                effective_datetime=value_datetime,
                posting_instructions=sentinel.posting_instructions,
                client_transactions=sentinel.client_transactions,
            ),
            denomination=sentinel.denomination,
            effective_date_client_transactions=None,
        )

        # assertions
        self.assertIsNone(result)
        mock_sum_client_transactions.assert_has_calls(
            calls=[
                call(
                    cutoff_datetime=value_datetime,
                    client_transactions=sentinel.client_transactions,
                    denomination=sentinel.denomination,
                ),
                call(
                    cutoff_datetime=CUT_OFF_DATE,
                    client_transactions=sentinel.effective_date_transactions,
                    denomination=sentinel.denomination,
                ),
            ]
        )

    def test_maximum_daily_withdrawal_exceeded_when_limit_has_been_partially_spent(
        self, mock_get_parameter: MagicMock, mock_sum_client_transactions: MagicMock
    ):
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)

        expected_rejection = Rejection(
            message=f"Transactions would cause the maximum daily withdrawal limit of "
            f"500 {DEFAULT_DENOMINATION} to be exceeded.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        # mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_daily_withdrawal": Decimal("500")}
        )
        mock_sum_client_transactions.side_effect = [
            (Decimal("0"), Decimal("100")),
            (Decimal("0"), Decimal("450")),
        ]

        # call to function
        result = maximum_daily_withdrawal.validate(
            vault=sentinel.vault,
            hook_arguments=PrePostingHookArguments(
                effective_datetime=value_datetime,
                posting_instructions=sentinel.posting_instructions,
                client_transactions=sentinel.client_transactions,
            ),
            denomination=DEFAULT_DENOMINATION,
            effective_date_client_transactions=sentinel.effective_date_transactions,
        )

        # assertions
        self.assertEqual(result, expected_rejection)
        mock_sum_client_transactions.assert_has_calls(
            calls=[
                call(
                    cutoff_datetime=value_datetime,
                    client_transactions=sentinel.client_transactions,
                    denomination=DEFAULT_DENOMINATION,
                ),
                call(
                    cutoff_datetime=CUT_OFF_DATE,
                    client_transactions=sentinel.effective_date_transactions,
                    denomination=DEFAULT_DENOMINATION,
                ),
            ]
        )
