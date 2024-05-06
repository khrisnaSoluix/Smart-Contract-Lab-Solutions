# standard libs
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.deposit.transaction_limits.deposit_limits import maximum_daily_deposit
from library.features.v4.deposit.transaction_limits.test.test_common_transaction_limit import (
    CUT_OFF_DATE,
    CommonTransactionLimitTest,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DENOMINATION
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PrePostingHookArguments,
    Rejection,
    RejectionReason,
)


@patch.object(maximum_daily_deposit.client_transaction_utils, "sum_client_transactions")
@patch.object(maximum_daily_deposit.utils, "get_parameter")
class TestMaximumDailyDepositLimit(CommonTransactionLimitTest):
    def test_maximum_daily_deposit_ignore_withdrawal(
        self, mock_get_parameter: MagicMock, mock_sum_client_transactions: MagicMock
    ):
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)

        # mocks
        mock_get_parameter.return_value = {}
        mock_sum_client_transactions.side_effect = [
            (Decimal("0"), Decimal("501")),
            (Decimal("0"), Decimal("0")),
        ]

        # call to the validation function
        result = maximum_daily_deposit.validate(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
            hook_arguments=PrePostingHookArguments(
                effective_datetime=value_datetime,
                posting_instructions=sentinel.posting_instructions,
                client_transactions=sentinel.client_transactions,
            ),
            effective_date_client_transactions={},
        )

        # assertions
        self.assertIsNone(result)
        mock_get_parameter.assert_not_called()

    def test_maximum_daily_deposit_exceeded(
        self, mock_get_parameter: MagicMock, mock_sum_client_transactions: MagicMock
    ):
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)
        expected_rejection = Rejection(
            message=f"Transactions would cause the maximum daily deposit limit of "
            f"500 {sentinel.denomination} to be exceeded.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        # mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_daily_deposit": Decimal("500")}
        )
        mock_sum_client_transactions.side_effect = [
            (Decimal("501"), Decimal("0")),
            (Decimal("0"), Decimal("0")),
        ]

        # call to the validation function
        result = maximum_daily_deposit.validate(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
            hook_arguments=PrePostingHookArguments(
                effective_datetime=value_datetime,
                posting_instructions=[sentinel.posting_instructions],
                client_transactions=sentinel.client_transaction,
            ),
            effective_date_client_transactions=sentinel.effective_date_transactions,
        )

        # assertions
        self.assertEqual(result, expected_rejection)
        mock_get_parameter.assert_called_once_with(
            vault=sentinel.vault, name="maximum_daily_deposit"
        )

    def test_maximum_daily_deposit_met(
        self, mock_get_parameter: MagicMock, mock_sum_client_transactions: MagicMock
    ):
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)

        # mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_daily_deposit": Decimal("500")}
        )
        mock_sum_client_transactions.side_effect = [
            (Decimal("300"), Decimal("0")),
            (Decimal("200"), Decimal("0")),
        ]

        # call to the validation function
        result = maximum_daily_deposit.validate(
            vault=sentinel.vault,
            denomination=DEFAULT_DENOMINATION,
            hook_arguments=PrePostingHookArguments(
                effective_datetime=value_datetime,
                posting_instructions=[sentinel.posting_instructions],
                client_transactions=sentinel.client_transactions,
            ),
            effective_date_client_transactions=sentinel.effective_date_transactions,
        )

        # assertions
        self.assertIsNone(result)

    def test_maximum_daily_deposit_met_transactions_not_provided(
        self, mock_get_parameter: MagicMock, mock_sum_client_transactions: MagicMock
    ):
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)

        # mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_daily_deposit": Decimal("500")}
        )
        mock_sum_client_transactions.side_effect = [
            (Decimal("300"), Decimal("0")),
            (Decimal("200"), Decimal("0")),
        ]
        mock_vault = self.create_mock(
            client_transactions_mapping=(
                {"EFFECTIVE_DATE_POSTINGS_FETCHER": sentinel.effective_date_transactions}
            )
        )

        # call to the validation function
        result = maximum_daily_deposit.validate(
            vault=mock_vault,
            denomination=sentinel.denomination,
            hook_arguments=PrePostingHookArguments(
                effective_datetime=value_datetime,
                posting_instructions=[sentinel.posting_instructions],
                client_transactions=sentinel.client_transactions,
            ),
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

    def test_maximum_daily_deposit_not_exceeded(
        self, mock_get_parameter: MagicMock, mock_sum_client_transactions: MagicMock
    ):
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)

        # mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_daily_deposit": Decimal("500")}
        )
        mock_sum_client_transactions.side_effect = [
            (Decimal("100"), Decimal("0")),
            (Decimal("200"), Decimal("0")),
        ]

        # call to the validation function
        result = maximum_daily_deposit.validate(
            vault=sentinel.vault,
            denomination=DEFAULT_DENOMINATION,
            hook_arguments=PrePostingHookArguments(
                effective_datetime=value_datetime,
                posting_instructions=[sentinel.posting_instructions],
                client_transactions=sentinel.client_transactions,
            ),
            effective_date_client_transactions=sentinel.effective_date_transactions,
        )

        # assertions
        self.assertIsNone(result)

    def test_maximum_daily_deposit_exceeded_reject_when_one_transaction_over_limit(
        self, mock_get_parameter: MagicMock, mock_sum_client_transactions: MagicMock
    ):
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)
        expected_rejection = Rejection(
            message=f"Transactions would cause the maximum daily deposit limit of "
            f"500 {sentinel.denomination} to be exceeded.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        # mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_daily_deposit": Decimal("500")}
        )
        mock_sum_client_transactions.side_effect = [
            (Decimal("100"), Decimal("0")),
            (Decimal("450"), Decimal("0")),
        ]

        # call to the validation function
        result = maximum_daily_deposit.validate(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
            hook_arguments=PrePostingHookArguments(
                effective_datetime=value_datetime,
                posting_instructions=[sentinel.posting_instructions],
                client_transactions=sentinel.client_transactions,
            ),
            effective_date_client_transactions=sentinel.effective_date_transactions,
        )

        # assertions
        self.assertEqual(result, expected_rejection)
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
