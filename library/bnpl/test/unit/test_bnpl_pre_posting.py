# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# library
import library.bnpl.contracts.template.bnpl as bnpl
from library.bnpl.test.unit.test_bnpl_common import BNPLTest

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import PrePostingHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DENOMINATION
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PrePostingHookResult,
    Rejection,
    RejectionReason,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelRejection,
)

DEFAULT_DATETIME = datetime(2023, 1, 1, tzinfo=bnpl.UTC_ZONE)


@patch.object(bnpl.utils, "is_force_override")
class PrePostingHookTest(BNPLTest):
    default_parameters = {
        bnpl.common_parameters.PARAM_DENOMINATION: DEFAULT_DENOMINATION,
    }

    @patch.object(bnpl.utils, "get_parameter")
    @patch.object(bnpl.utils, "validate_denomination")
    @patch.object(bnpl.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(bnpl.utils, "get_available_balance")
    def test_pre_posting_hook_rejects_debits(
        self,
        mock_get_available_balance: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        # construct expected result
        expected = PrePostingHookResult(
            rejection=Rejection(
                message="Debiting from this account is not allowed.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )

        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.default_parameters
        )
        mock_vault = self.create_mock()
        mock_is_force_override.return_value = False
        mock_validate_denomination.return_value = None
        mock_validate_single_hard_settlement.return_value = None
        mock_get_available_balance.return_value = Decimal("1000")
        mock_posting = MagicMock()
        mock_posting.balances.return_value = sentinel.balances

        # run function
        hook_args = PrePostingHookArguments(
            posting_instructions=[mock_posting],
            effective_datetime=DEFAULT_DATETIME,
            client_transactions={},
        )
        result = bnpl.pre_posting_hook(mock_vault, hook_args)

        # validate results
        self.assertEqual(result, expected)

    @patch.object(bnpl.utils, "get_parameter")
    @patch.object(bnpl.utils, "validate_denomination")
    @patch.object(bnpl.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(bnpl.utils, "get_available_balance")
    @patch.object(bnpl.derived_params, "get_total_outstanding_debt")
    @patch.object(bnpl.derived_params, "get_total_due_amount")
    def test_pre_posting_hook_rejects_payment_more_than_owed(
        self,
        mock_get_total_due_amount: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_get_available_balance: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        # construct expected result
        expected = PrePostingHookResult(
            rejection=Rejection(
                message="Cannot pay more than what is owed.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )

        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.default_parameters
        )
        mock_balances_observation = SentinelBalancesObservation("dummy_balances_observation")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                bnpl.fetchers.LIVE_BALANCES_BOF_ID: mock_balances_observation
            }
        )
        mock_is_force_override.return_value = False
        mock_validate_denomination.return_value = None
        mock_validate_single_hard_settlement.return_value = None
        mock_get_total_outstanding_debt.return_value = Decimal("777")
        mock_get_total_due_amount.return_value = Decimal("144")
        mock_get_available_balance.return_value = Decimal("-1000")
        mock_posting = MagicMock()
        mock_posting.balances.return_value = sentinel.balances

        # run function
        hook_args = PrePostingHookArguments(
            posting_instructions=[mock_posting],
            effective_datetime=DEFAULT_DATETIME,
            client_transactions={},
        )
        result = bnpl.pre_posting_hook(mock_vault, hook_args)

        # validate results
        self.assertEqual(result, expected)

    @patch.object(bnpl.utils, "get_parameter")
    def test_pre_posting_hook_returns_none_for_force_override(
        self,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        # construct expected result
        expected = None

        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.default_parameters
        )
        mock_vault = self.create_mock()
        mock_is_force_override.return_value = True

        # run function
        hook_args = PrePostingHookArguments(
            posting_instructions=sentinel.posting_instructions,
            effective_datetime=DEFAULT_DATETIME,
            client_transactions={},
        )
        result = bnpl.pre_posting_hook(mock_vault, hook_args)

        # validate results
        self.assertEqual(result, expected)

    @patch.object(bnpl.utils, "get_parameter")
    @patch.object(bnpl.utils, "validate_denomination")
    @patch.object(bnpl.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(bnpl.utils, "get_available_balance")
    @patch.object(bnpl.derived_params, "get_total_outstanding_debt")
    @patch.object(bnpl.derived_params, "get_total_due_amount")
    def test_pre_posting_hook_rejects_payment_more_than_due(
        self,
        mock_get_total_due_amount: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_get_available_balance: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        # construct expected result
        expected = PrePostingHookResult(
            rejection=Rejection(
                message="Cannot pay more than what is due.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )
        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.default_parameters
        )
        mock_balances_observation = SentinelBalancesObservation("dummy_balances_observation")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                bnpl.fetchers.LIVE_BALANCES_BOF_ID: mock_balances_observation
            }
        )
        mock_is_force_override.return_value = False
        mock_validate_denomination.return_value = None
        mock_validate_single_hard_settlement.return_value = None
        mock_get_total_outstanding_debt.return_value = Decimal("777")
        mock_get_total_due_amount.return_value = Decimal("144")
        mock_get_available_balance.return_value = Decimal("-200")
        mock_posting = MagicMock()
        mock_posting.balances.return_value = sentinel.balances

        # run function
        hook_args = PrePostingHookArguments(
            posting_instructions=[mock_posting],
            effective_datetime=DEFAULT_DATETIME,
            client_transactions={},
        )
        result = bnpl.pre_posting_hook(mock_vault, hook_args)

        # validate results
        self.assertEqual(result, expected)

    @patch.object(bnpl.utils, "get_parameter")
    @patch.object(bnpl.utils, "validate_denomination")
    @patch.object(bnpl.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(bnpl.utils, "get_available_balance")
    @patch.object(bnpl.derived_params, "get_total_outstanding_debt")
    @patch.object(bnpl.derived_params, "get_total_due_amount")
    def test_pre_posting_hook_returns_none_for_valid_payment(
        self,
        mock_get_total_due_amount: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_get_available_balance: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        # construct expected result
        expected = None

        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.default_parameters
        )
        mock_balances_observation = SentinelBalancesObservation("dummy_balances_observation")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                bnpl.fetchers.LIVE_BALANCES_BOF_ID: mock_balances_observation
            }
        )
        mock_is_force_override.return_value = False
        mock_validate_denomination.return_value = None
        mock_validate_single_hard_settlement.return_value = None
        mock_get_total_outstanding_debt.return_value = Decimal("777")
        mock_get_total_due_amount.return_value = Decimal("144")
        mock_get_available_balance.return_value = Decimal("-144")

        mock_posting = MagicMock()
        mock_posting.balances.return_value = sentinel.balances

        # run function
        hook_args = PrePostingHookArguments(
            posting_instructions=[mock_posting],
            effective_datetime=DEFAULT_DATETIME,
            client_transactions={},
        )
        result = bnpl.pre_posting_hook(mock_vault, hook_args)

        # validate results
        self.assertEqual(result, expected)

    @patch.object(bnpl.utils, "get_parameter")
    @patch.object(bnpl.utils, "validate_denomination")
    def test_pre_posting_hook_rejects_invalid_denomination(
        self,
        mock_validate_denomination: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        # expected values
        mock_rejection = SentinelRejection("dummy_rejection")

        # construct expected result
        expected = PrePostingHookResult(rejection=mock_rejection)

        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.default_parameters
        )
        mock_vault = self.create_mock()
        mock_is_force_override.return_value = False
        mock_validate_denomination.return_value = mock_rejection

        # run function
        hook_args = PrePostingHookArguments(
            posting_instructions=sentinel.posting_instructions,
            effective_datetime=DEFAULT_DATETIME,
            client_transactions={},
        )
        result = bnpl.pre_posting_hook(mock_vault, hook_args)

        # validate results
        self.assertEqual(result, expected)

    @patch.object(bnpl.utils, "get_parameter")
    @patch.object(bnpl.utils, "validate_denomination")
    @patch.object(bnpl.utils, "validate_single_hard_settlement_or_transfer")
    def test_pre_posting_hook_rejects_non_single_hard_settlement(
        self,
        mock_validate_single_hard_settlement: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        # expected values
        mock_rejection = SentinelRejection("dummy_rejection")

        # construct expected result
        expected = PrePostingHookResult(rejection=mock_rejection)

        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.default_parameters
        )
        mock_vault = self.create_mock()
        mock_is_force_override.return_value = False
        mock_validate_denomination.return_value = None
        mock_validate_single_hard_settlement.return_value = mock_rejection

        # run function
        hook_args = PrePostingHookArguments(
            posting_instructions=sentinel.posting_instructions,
            effective_datetime=DEFAULT_DATETIME,
            client_transactions={},
        )
        result = bnpl.pre_posting_hook(mock_vault, hook_args)

        # validate results
        self.assertEqual(result, expected)

    @patch.object(bnpl.utils, "get_parameter")
    @patch.object(bnpl.utils, "validate_denomination")
    @patch.object(bnpl.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(bnpl.utils, "get_available_balance")
    def test_pre_posting_hook_rejects_zero_amount(
        self,
        mock_get_available_balance: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        # construct expected result
        expected = PrePostingHookResult(
            rejection=Rejection(
                message="Cannot post zero amount.",
                reason_code=RejectionReason.CLIENT_CUSTOM_REASON,
            )
        )

        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.default_parameters
        )
        mock_vault = self.create_mock()
        mock_is_force_override.return_value = False
        mock_validate_denomination.return_value = None
        mock_validate_single_hard_settlement.return_value = None
        mock_get_available_balance.return_value = Decimal("0")
        mock_posting = MagicMock()
        mock_posting.balances.return_value = sentinel.balances

        # run function
        hook_args = PrePostingHookArguments(
            posting_instructions=[mock_posting],
            effective_datetime=DEFAULT_DATETIME,
            client_transactions={},
        )
        result = bnpl.pre_posting_hook(mock_vault, hook_args)

        # validate results
        self.assertEqual(result, expected)
