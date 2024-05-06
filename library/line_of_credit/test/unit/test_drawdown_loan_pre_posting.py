# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
from library.line_of_credit.contracts.template import drawdown_loan
from library.line_of_credit.test.unit.test_drawdown_loan_common import (
    DEFAULT_DATETIME,
    DrawdownLoanTestBase,
)

# contracts api
from contracts_api import PrePostingHookArguments, RejectionReason

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PrePostingHookResult,
    Rejection,
)


@patch.object(drawdown_loan.utils, "is_force_override")
class DrawdownLoanPrePostingTest(DrawdownLoanTestBase):
    def test_force_override_returns_none(self, mock_is_force_override: MagicMock):
        mock_is_force_override.return_value = True

        result = drawdown_loan.pre_posting_hook(
            vault=sentinel.vault,
            hook_arguments=PrePostingHookArguments(
                effective_datetime=DEFAULT_DATETIME,
                posting_instructions=[sentinel.posting_instructions],
                client_transactions={},
            ),
        )

        self.assertIsNone(result)

        mock_is_force_override.assert_called_once_with(
            posting_instructions=[sentinel.posting_instructions]
        )

    def test_no_force_override_returns_rejection(self, mock_is_force_override: MagicMock):
        mock_is_force_override.return_value = False

        result = drawdown_loan.pre_posting_hook(
            vault=sentinel.vault,
            hook_arguments=PrePostingHookArguments(
                effective_datetime=DEFAULT_DATETIME,
                posting_instructions=[sentinel.posting_instructions],
                client_transactions={},
            ),
        )

        self.assertEqual(
            result,
            PrePostingHookResult(
                rejection=Rejection(
                    message="All postings should be made to the Line of Credit account",
                    reason_code=RejectionReason.CLIENT_CUSTOM_REASON,
                )
            ),
        )

        mock_is_force_override.assert_called_once_with(
            posting_instructions=[sentinel.posting_instructions]
        )
