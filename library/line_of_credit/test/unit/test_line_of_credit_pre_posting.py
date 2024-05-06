# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# library
from library.line_of_credit.contracts.template import line_of_credit
from library.line_of_credit.test.unit.test_line_of_credit_common import (
    DEFAULT_DATETIME,
    LineOfCreditTestBase,
)

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import PrePostingHookArguments, RejectionReason

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PrePostingHookResult,
    Rejection,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelRejection,
)


@patch.object(line_of_credit.utils, "is_force_override")
@patch.object(line_of_credit.utils, "get_parameter")
class LineOfCreditPrePostingTest(LineOfCreditTestBase):
    common_hook_args_sentinel_posting = PrePostingHookArguments(
        effective_datetime=DEFAULT_DATETIME,
        posting_instructions=[sentinel.posting_instructions],
        client_transactions={},
    )
    common_param_return_values = {
        "denomination": sentinel.denomination,
    }

    def test_force_override_returns_none(
        self,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        mock_is_force_override.return_value = True

        result = line_of_credit.pre_posting_hook(
            vault=sentinel.vault, hook_arguments=self.common_hook_args_sentinel_posting
        )

        self.assertIsNone(result)

        mock_is_force_override.assert_called_once_with(
            posting_instructions=[sentinel.posting_instructions]
        )

    @patch.object(line_of_credit.utils, "validate_single_hard_settlement_or_transfer")
    def test_multiple_postings_return_rejection(
        self,
        mock_validate_single_hard_settlement: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        mock_is_force_override.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )

        posting_rejection = SentinelRejection("denomination_rejection")
        mock_validate_single_hard_settlement.return_value = posting_rejection

        result = line_of_credit.pre_posting_hook(
            vault=sentinel.vault, hook_arguments=self.common_hook_args_sentinel_posting
        )

        expected = PrePostingHookResult(rejection=posting_rejection)
        self.assertEqual(result, expected)

    @patch.object(line_of_credit.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(line_of_credit.utils, "validate_denomination")
    def test_wrong_denomination_returns_rejection(
        self,
        mock_validate_denomination: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )

        denomination_rejection = SentinelRejection("denomination_rejection")
        mock_validate_denomination.return_value = denomination_rejection

        result = line_of_credit.pre_posting_hook(
            vault=sentinel.vault, hook_arguments=self.common_hook_args_sentinel_posting
        )

        expected = PrePostingHookResult(rejection=denomination_rejection)

        self.assertEqual(result, expected)

    @patch.object(line_of_credit.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(line_of_credit.utils, "validate_denomination")
    @patch.object(line_of_credit.utils, "validate_amount_precision")
    def test_wrong_amount_precision_returns_rejection(
        self,
        mock_validate_amount_precision: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = None
        mock_validate_denomination.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )

        posting_rejection = SentinelRejection("posting_rejection")
        mock_validate_amount_precision.return_value = posting_rejection

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[self.outbound_hard_settlement(amount=Decimal("3"))],
            client_transactions={},
        )

        result = line_of_credit.pre_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)

        expected = PrePostingHookResult(rejection=posting_rejection)

        self.assertEqual(result, expected)

    @patch.object(line_of_credit.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(line_of_credit.utils, "validate_denomination")
    @patch.object(line_of_credit.utils, "validate_amount_precision")
    @patch.object(line_of_credit.minimum_loan_principal, "validate")
    def test_loan_creation_posting_triggers_minimum_loan_amount_rejection(
        self,
        mock_validate_minimum_loan_amount: MagicMock,
        mock_validate_amount_precision: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = None
        mock_validate_denomination.return_value = None
        mock_validate_amount_precision.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )

        rejection = SentinelRejection("minimum_loan_amount_rejection")
        mock_validate_minimum_loan_amount.return_value = rejection

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=Decimal("3"), denomination=sentinel.denomination
                )
            ],
            client_transactions={},
        )

        result = line_of_credit.pre_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)

        expected = PrePostingHookResult(rejection=rejection)

        self.assertEqual(result, expected)

    @patch.object(line_of_credit.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(line_of_credit.utils, "validate_denomination")
    @patch.object(line_of_credit.utils, "validate_amount_precision")
    @patch.object(line_of_credit.minimum_loan_principal, "validate")
    @patch.object(line_of_credit.maximum_loan_principal, "validate")
    def test_loan_creation_posting_triggers_maximum_loan_amount_rejection(
        self,
        mock_validate_maximum_loan_amount: MagicMock,
        mock_validate_minimum_loan_amount: MagicMock,
        mock_validate_amount_precision: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = None
        mock_validate_denomination.return_value = None
        mock_validate_amount_precision.return_value = None
        mock_validate_minimum_loan_amount.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )

        rejection = SentinelRejection("maximum_loan_amount_rejection")
        mock_validate_maximum_loan_amount.return_value = rejection

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=Decimal("3"), denomination=sentinel.denomination
                )
            ],
            client_transactions={},
        )

        result = line_of_credit.pre_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)

        expected = PrePostingHookResult(rejection=rejection)

        self.assertEqual(result, expected)

    @patch.object(line_of_credit.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(line_of_credit.utils, "validate_denomination")
    @patch.object(line_of_credit.utils, "validate_amount_precision")
    @patch.object(line_of_credit.repayment_holiday, "is_repayment_blocked")
    def test_repayment_no_repayment_holiday_returns_none(
        self,
        mock_is_repayment_blocked: MagicMock,
        mock_validate_amount_precision: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = None
        mock_validate_denomination.return_value = None
        mock_validate_amount_precision.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )
        mock_is_repayment_blocked.return_value = False

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[
                self.inbound_hard_settlement(
                    amount=Decimal("3"), denomination=sentinel.denomination
                )
            ],
            client_transactions={},
        )

        result = line_of_credit.pre_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)

        self.assertIsNone(result)
        mock_is_repayment_blocked.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
        )

    @patch.object(line_of_credit.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(line_of_credit.utils, "validate_denomination")
    @patch.object(line_of_credit.utils, "validate_amount_precision")
    @patch.object(line_of_credit.repayment_holiday, "is_repayment_blocked")
    def test_repayment_with_repayment_holiday_returns_rejection(
        self,
        mock_is_repayment_blocked: MagicMock,
        mock_validate_amount_precision: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = None
        mock_validate_denomination.return_value = None
        mock_validate_amount_precision.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )
        mock_is_repayment_blocked.return_value = True

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[
                self.inbound_hard_settlement(
                    amount=Decimal("3"), denomination=sentinel.denomination
                )
            ],
            client_transactions={},
        )

        expected = PrePostingHookResult(
            rejection=Rejection(
                message="Repayments blocked for this account",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )

        result = line_of_credit.pre_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)

        self.assertEqual(result, expected)
        mock_is_repayment_blocked.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
        )
