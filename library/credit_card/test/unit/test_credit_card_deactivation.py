# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# library
from library.credit_card.contracts.template import credit_card
from library.credit_card.test.unit.test_credit_card_common import CreditCardTestBase

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import (
    DEFAULT_ASSET,
    BalanceCoordinate,
    BalanceDefaultDict,
    BalancesObservation,
    Phase,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    Balance,
    DeactivationHookArguments,
    DeactivationHookResult,
    PostingInstructionsDirective,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelAccountNotificationDirective,
    SentinelCustomInstruction,
    SentinelRejection,
)

# Addresses
FULL_OUTSTANDING_BALANCE = "FULL_OUTSTANDING_BALANCE"
full_outstanding_balance = Balance(credit=Decimal(0), debit=Decimal(10), net=Decimal(10))
fob_coordinate = BalanceCoordinate(
    account_address=credit_card.FULL_OUTSTANDING_BALANCE,
    asset=DEFAULT_ASSET,
    denomination=sentinel.denomination,
    phase=Phase.COMMITTED,
)
live_observation = BalancesObservation(
    balances=BalanceDefaultDict(mapping={fob_coordinate: full_outstanding_balance})
)


@patch.object(credit_card.utils, "get_parameter")
@patch.object(credit_card.utils, "is_flag_in_list_applied")
@patch.object(credit_card, "_get_supported_txn_types")
@patch.object(credit_card, "_can_final_statement_be_generated")
@patch.object(credit_card, "_process_write_off")
@patch.object(credit_card, "_process_statement_cut_off")
@patch.object(credit_card, "_zero_out_balances_for_account_closure")
class DeactivationHookTests(CreditCardTestBase):
    # define common return types to avoid duplicated definitions across tests
    common_get_param_return_values = {
        "denomination": sentinel.denomination,
    }

    test_posting_ci = [SentinelCustomInstruction("test_posting_ci")]
    test_account_notification = [SentinelAccountNotificationDirective("test_account_notification")]

    mock_posting_directive = [
        PostingInstructionsDirective(
            posting_instructions=test_posting_ci,
            value_datetime=DEFAULT_DATETIME,
            client_batch_id="CLOSE_ACCOUNT-MOCK_HOOK",
        )
    ]

    def test_deactivation_hook_fails_if_final_statement_cant_be_generated(
        self,
        mock_zero_out_balances_for_account_closure: MagicMock,
        mock_process_statement_cut_off: MagicMock,
        mock_process_write_off: MagicMock,
        mock_can_final_statement_be_generated: MagicMock,
        mock_get_supported_txn_types: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                credit_card.LIVE_BALANCES_BOF_ID: live_observation
            },
        )

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={**self.common_get_param_return_values}
        )
        mock_is_flag_in_list_applied.side_effect = [True, False]
        rejection = SentinelRejection("dummy_rejection")
        mock_can_final_statement_be_generated.return_value = rejection
        mock_get_supported_txn_types.return_value = {"test": ["test"]}
        mock_process_statement_cut_off.return_value = ([], [])
        mock_zero_out_balances_for_account_closure.return_value = []

        hook_args = DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)

        hook_result = credit_card.deactivation_hook(vault=mock_vault, hook_arguments=hook_args)

        expected_result = DeactivationHookResult(rejection=rejection)

        mock_process_write_off.assert_not_called()
        self.assertEqual(hook_result, expected_result)

    def test_deactivation_hook_generates_postings_when_account_is_deactivated(
        self,
        mock_zero_out_balances_for_account_closure: MagicMock,
        mock_process_statement_cut_off: MagicMock,
        mock_process_write_off: MagicMock,
        mock_can_final_statement_be_generated: MagicMock,
        mock_get_supported_txn_types: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                credit_card.LIVE_BALANCES_BOF_ID: live_observation
            },
        )

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={**self.common_get_param_return_values}
        )
        mock_is_flag_in_list_applied.side_effect = [True, True]
        mock_can_final_statement_be_generated.return_value = None
        mock_get_supported_txn_types.return_value = {}
        mock_process_write_off.return_value = []
        mock_process_statement_cut_off.return_value = (
            self.test_account_notification,
            self.mock_posting_directive,
        )
        mock_zero_out_balances_for_account_closure.return_value = []

        hook_args = DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)

        hook_result = credit_card.deactivation_hook(vault=mock_vault, hook_arguments=hook_args)

        expected_result = DeactivationHookResult(
            account_notification_directives=self.test_account_notification,
            posting_instructions_directives=self.mock_posting_directive,
        )

        self.assertEqual(hook_result, expected_result)

    def test_write_off_occurs_if_write_off_flag_is_present(
        self,
        mock_zero_out_balances_for_account_closure: MagicMock,
        mock_process_statement_cut_off: MagicMock,
        mock_process_write_off: MagicMock,
        mock_can_final_statement_be_generated: MagicMock,
        mock_get_supported_txn_types: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                credit_card.LIVE_BALANCES_BOF_ID: live_observation
            },
        )

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={**self.common_get_param_return_values}
        )
        mock_is_flag_in_list_applied.side_effect = [True, True]
        mock_can_final_statement_be_generated.return_value = None
        mock_get_supported_txn_types.return_value = {}
        mock_process_write_off.return_value = self.test_posting_ci
        mock_process_statement_cut_off.return_value = (self.test_account_notification, [])
        mock_zero_out_balances_for_account_closure.return_value = []

        hook_args = DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)

        hook_result = credit_card.deactivation_hook(vault=mock_vault, hook_arguments=hook_args)

        expected_result = DeactivationHookResult(
            account_notification_directives=self.test_account_notification,
            posting_instructions_directives=self.mock_posting_directive,
        )

        self.assertEqual(hook_result, expected_result)
        mock_process_write_off.assert_called_with(
            mock_vault,
            sentinel.denomination,
            {fob_coordinate: full_outstanding_balance},
            DEFAULT_DATETIME,
        )
