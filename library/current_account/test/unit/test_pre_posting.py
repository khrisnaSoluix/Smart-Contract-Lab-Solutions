# standard libs
from unittest.mock import MagicMock, call, patch, sentinel

# library
from library.current_account.test.unit.current_account_common import (
    DEFAULT_DATE,
    CurrentAccountTest,
    current_account,
)

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PrePostingHookArguments,
    PrePostingHookResult,
    Rejection,
    RejectionReason,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelCustomInstruction,
    SentinelRejection,
)


class PrePostingHookTest(CurrentAccountTest):
    @patch.object(current_account.utils, "is_force_override")
    def test_when_force_override_is_active_posting_instructions_are_accepted(
        self, mock_is_force_override: MagicMock
    ):
        postings = [SentinelCustomInstruction("dummy_posting")]

        # setup mocks
        mock_is_force_override.return_value = True
        mock_vault = sentinel.vault

        # hook call
        hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATE, posting_instructions=postings, client_transactions={}
        )
        hook_result = current_account.pre_posting_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )

        # assertions
        self.assertIsNone(hook_result)
        mock_is_force_override.assert_called_once_with(posting_instructions=postings)

    @patch.object(current_account.utils, "is_flag_in_list_applied")
    @patch.object(current_account.utils, "is_force_override")
    def test_rejects_postings_when_dormant(
        self, mock_is_force_override: MagicMock, mock_is_flag_in_list_applied: MagicMock
    ):
        postings = [SentinelCustomInstruction("dummy_posting")]

        # setup mocks
        mock_is_force_override.return_value = False
        mock_is_flag_in_list_applied.return_value = True
        mock_vault = sentinel.vault

        # expected results
        expected_result = PrePostingHookResult(
            rejection=Rejection(
                message="Account flagged 'Dormant' does not accept external transactions.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )

        # hook call
        hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATE, posting_instructions=postings, client_transactions={}
        )
        hook_result = current_account.pre_posting_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )

        # assertions
        mock_is_flag_in_list_applied.assert_called_once_with(
            vault=mock_vault, parameter_name="dormancy_flags", effective_datetime=DEFAULT_DATE
        )
        self.assertEqual(hook_result, expected_result)

    @patch.object(current_account.utils, "validate_denomination")
    @patch.object(current_account.utils, "get_parameter")
    @patch.object(current_account.utils, "is_flag_in_list_applied")
    @patch.object(current_account.utils, "is_force_override")
    def test_rejects_postings_when_denomination_is_not_supported(
        self,
        mock_is_force_override: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_validate_denomination: MagicMock,
    ):
        postings = [SentinelCustomInstruction("dummy_posting")]
        rejection = SentinelRejection("dummy_rejection")

        # setup mocks
        mock_is_force_override.return_value = False
        mock_is_flag_in_list_applied.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP", "additional_denominations": ["EUR", "USD"]}
        )
        mock_validate_denomination.return_value = rejection
        mock_vault = sentinel.vault

        # hook call
        hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATE, posting_instructions=postings, client_transactions={}
        )
        hook_result = current_account.pre_posting_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )

        # assertions
        self.assertEqual(hook_result, PrePostingHookResult(rejection=rejection))
        mock_get_parameter.assert_has_calls(
            [
                call(vault=mock_vault, name="denomination", at_datetime=DEFAULT_DATE),
                call(vault=mock_vault, name="additional_denominations", is_json=True),
            ]
        )
        mock_validate_denomination.assert_called_with(
            posting_instructions=postings, accepted_denominations=["EUR", "USD", "GBP"]
        )

    @patch.object(current_account.available_balance, "validate")
    @patch.object(current_account.utils, "validate_denomination")
    @patch.object(current_account.utils, "get_parameter")
    @patch.object(current_account.utils, "is_flag_in_list_applied")
    @patch.object(current_account.utils, "is_force_override")
    def test_rejects_postings_when_maximum_balance_is_surpassed_additional_denomination(
        self,
        mock_is_force_override: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_available_balance_validate: MagicMock,
    ):
        postings = [SentinelCustomInstruction("dummy_posting")]
        rejection = SentinelRejection("dummy_rejection")

        # setup mocks
        mock_is_force_override.return_value = False
        mock_is_flag_in_list_applied.return_value = False
        mock_validate_denomination.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP", "additional_denominations": ["USD"]}
        )
        mock_available_balance_validate.return_value = rejection

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                "live_balances_bof": SentinelBalancesObservation("dummy_observation")
            }
        )

        # hook call
        hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATE, posting_instructions=postings, client_transactions={}
        )
        hook_result = current_account.pre_posting_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )

        # assertions
        self.assertEqual(hook_result, PrePostingHookResult(rejection=rejection))
        mock_available_balance_validate.assert_called_once_with(
            balances=sentinel.balances_dummy_observation,
            denominations=["USD"],
            posting_instructions=postings,
        )

    @patch.object(current_account.available_balance, "validate")
    @patch.object(current_account.overdraft_limit, "validate")
    @patch.object(current_account.utils, "validate_denomination")
    @patch.object(current_account.utils, "get_parameter")
    @patch.object(current_account.utils, "is_flag_in_list_applied")
    @patch.object(current_account.utils, "is_force_override")
    def test_rejects_postings_when_overdraft_limit_is_surpassed(
        self,
        mock_is_force_override: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_overdraft_limit: MagicMock,
        mock_available_balance_validate: MagicMock,
    ):
        postings = [SentinelCustomInstruction("dummy_posting")]
        rejection = SentinelRejection("dummy_rejection")

        # setup mocks
        mock_is_force_override.return_value = False
        mock_is_flag_in_list_applied.return_value = False
        mock_validate_denomination.return_value = None
        mock_available_balance_validate.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP", "additional_denominations": []}
        )
        mock_validate_overdraft_limit.return_value = rejection
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                "live_balances_bof": SentinelBalancesObservation("dummy_observation")
            }
        )

        # hook call
        hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATE, posting_instructions=postings, client_transactions={}
        )
        hook_result = current_account.pre_posting_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )

        # assertions
        self.assertEqual(hook_result, PrePostingHookResult(rejection=rejection))
        mock_validate_overdraft_limit.assert_called_once_with(
            vault=mock_vault,
            postings=postings,
            denomination=self.default_denomination,
            balances=sentinel.balances_dummy_observation,
        )

    @patch.object(current_account.available_balance, "validate")
    @patch.object(current_account.minimum_single_deposit_limit, "validate")
    @patch.object(current_account.overdraft_limit, "validate")
    @patch.object(current_account.utils, "validate_denomination")
    @patch.object(current_account.utils, "get_parameter")
    @patch.object(current_account.utils, "is_flag_in_list_applied")
    @patch.object(current_account.utils, "is_force_override")
    def test_rejects_postings_when_minimum_single_deposit_is_not_met(
        self,
        mock_is_force_override: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_overdraft_limit: MagicMock,
        mock_validate_minimum_single_deposit_limit: MagicMock,
        mock_available_balance_validate: MagicMock,
    ):
        postings = [SentinelCustomInstruction("dummy_posting")]
        rejection = SentinelRejection("dummy_rejection")

        # setup mocks
        mock_is_force_override.return_value = False
        mock_is_flag_in_list_applied.return_value = False
        mock_validate_denomination.return_value = None
        mock_available_balance_validate.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP", "additional_denominations": []}
        )
        mock_validate_overdraft_limit.return_value = None
        mock_validate_minimum_single_deposit_limit.return_value = rejection
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                "live_balances_bof": SentinelBalancesObservation("dummy_observation")
            }
        )

        # hook call
        hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATE, posting_instructions=postings, client_transactions={}
        )
        hook_result = current_account.pre_posting_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )

        # assertions
        self.assertEqual(hook_result, PrePostingHookResult(rejection=rejection))
        mock_validate_minimum_single_deposit_limit.assert_called_once_with(
            vault=mock_vault,
            postings=postings,
            denomination=self.default_denomination,
        )

    @patch.object(current_account.available_balance, "validate")
    @patch.object(current_account.minimum_single_withdrawal_limit, "validate")
    @patch.object(current_account.minimum_single_deposit_limit, "validate")
    @patch.object(current_account.overdraft_limit, "validate")
    @patch.object(current_account.utils, "validate_denomination")
    @patch.object(current_account.utils, "get_parameter")
    @patch.object(current_account.utils, "is_flag_in_list_applied")
    @patch.object(current_account.utils, "is_force_override")
    def test_rejects_postings_when_minimum_single_withdrawal_is_not_met(
        self,
        mock_is_force_override: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_overdraft_limit: MagicMock,
        mock_validate_minimum_single_deposit_limit: MagicMock,
        mock_validate_minimum_single_withdrawal_limit: MagicMock,
        mock_available_balance_validate: MagicMock,
    ):
        postings = [SentinelCustomInstruction("dummy_posting")]
        rejection = SentinelRejection("dummy_rejection")

        # setup mocks
        mock_is_force_override.return_value = False
        mock_is_flag_in_list_applied.return_value = False
        mock_validate_denomination.return_value = None
        mock_available_balance_validate.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP", "additional_denominations": []}
        )
        mock_validate_overdraft_limit.return_value = None
        mock_validate_minimum_single_deposit_limit.return_value = None
        mock_validate_minimum_single_withdrawal_limit.return_value = rejection

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                "live_balances_bof": SentinelBalancesObservation("dummy_observation")
            }
        )

        # hook call
        hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATE, posting_instructions=postings, client_transactions={}
        )
        hook_result = current_account.pre_posting_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )

        # assertions
        self.assertEqual(hook_result, PrePostingHookResult(rejection=rejection))
        mock_validate_minimum_single_withdrawal_limit.assert_called_once_with(
            vault=mock_vault,
            postings=postings,
            denomination=self.default_denomination,
        )

    @patch.object(current_account.available_balance, "validate")
    @patch.object(current_account.maximum_balance_limit, "validate")
    @patch.object(current_account.minimum_single_withdrawal_limit, "validate")
    @patch.object(current_account.minimum_single_deposit_limit, "validate")
    @patch.object(current_account.overdraft_limit, "validate")
    @patch.object(current_account.utils, "validate_denomination")
    @patch.object(current_account.utils, "get_parameter")
    @patch.object(current_account.utils, "is_flag_in_list_applied")
    @patch.object(current_account.utils, "is_force_override")
    def test_rejects_postings_when_maximum_balance_is_surpassed(
        self,
        mock_is_force_override: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_overdraft_limit: MagicMock,
        mock_validate_minimum_single_deposit_limit: MagicMock,
        mock_validate_minimum_single_withdrawal_limit: MagicMock,
        mock_validate_maximum_balance_limit: MagicMock,
        mock_available_balance_validate: MagicMock,
    ):
        postings = [SentinelCustomInstruction("dummy_posting")]
        rejection = SentinelRejection("dummy_rejection")

        # setup mocks
        mock_is_force_override.return_value = False
        mock_is_flag_in_list_applied.return_value = False
        mock_validate_denomination.return_value = None
        mock_available_balance_validate.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP", "additional_denominations": []}
        )
        mock_validate_overdraft_limit.return_value = None
        mock_validate_minimum_single_deposit_limit.return_value = None
        mock_validate_minimum_single_withdrawal_limit.return_value = None
        mock_validate_maximum_balance_limit.return_value = rejection

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                "live_balances_bof": SentinelBalancesObservation("dummy_observation")
            }
        )

        # hook call
        hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATE, posting_instructions=postings, client_transactions={}
        )
        hook_result = current_account.pre_posting_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )

        # assertions
        self.assertEqual(hook_result, PrePostingHookResult(rejection=rejection))
        mock_validate_maximum_balance_limit.assert_called_once_with(
            vault=mock_vault,
            postings=postings,
            denomination=self.default_denomination,
            balances=sentinel.balances_dummy_observation,
        )

    @patch.object(current_account.maximum_daily_withdrawal, "validate")
    @patch.object(current_account.available_balance, "validate")
    @patch.object(current_account.maximum_balance_limit, "validate")
    @patch.object(current_account.minimum_single_withdrawal_limit, "validate")
    @patch.object(current_account.minimum_single_deposit_limit, "validate")
    @patch.object(current_account.overdraft_limit, "validate")
    @patch.object(current_account.utils, "validate_denomination")
    @patch.object(current_account.utils, "get_parameter")
    @patch.object(current_account.utils, "is_flag_in_list_applied")
    @patch.object(current_account.utils, "is_force_override")
    def test_rejects_postings_when_maximum_daily_withdrawal_limit_is_surpassed(
        self,
        mock_is_force_override: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_overdraft_limit: MagicMock,
        mock_validate_minimum_single_deposit_limit: MagicMock,
        mock_validate_minimum_single_withdrawal_limit: MagicMock,
        mock_validate_maximum_balance_limit: MagicMock,
        mock_available_balance_validate: MagicMock,
        mock_validate_maximum_daily_withdrawal: MagicMock,
    ):
        postings = [SentinelCustomInstruction("dummy_posting")]
        rejection = SentinelRejection("dummy_rejection")

        # setup mocks
        mock_is_force_override.return_value = False
        mock_is_flag_in_list_applied.return_value = False
        mock_validate_denomination.return_value = None
        mock_available_balance_validate.return_value = None
        mock_validate_minimum_single_deposit_limit.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP", "additional_denominations": []}
        )
        mock_validate_overdraft_limit.return_value = None
        mock_validate_minimum_single_withdrawal_limit.return_value = None
        mock_validate_maximum_balance_limit.return_value = None
        mock_validate_maximum_daily_withdrawal.return_value = rejection

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                "live_balances_bof": SentinelBalancesObservation("dummy_observation")
            },
            client_transactions_mapping={
                "EFFECTIVE_DATE_POSTINGS_FETCHER": sentinel.effective_date_transactions
            },
        )

        # hook call
        hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATE,
            posting_instructions=postings,
            client_transactions=sentinel.proposed_client_transactions,
        )
        hook_result = current_account.pre_posting_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )

        # assertions
        self.assertEqual(hook_result, PrePostingHookResult(rejection=rejection))
        mock_validate_maximum_daily_withdrawal.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_arguments,
            denomination=self.default_denomination,
            effective_date_client_transactions=sentinel.effective_date_transactions,
        )

    @patch.object(current_account.maximum_daily_deposit_limit, "validate")
    @patch.object(current_account.maximum_daily_withdrawal, "validate")
    @patch.object(current_account.available_balance, "validate")
    @patch.object(current_account.maximum_balance_limit, "validate")
    @patch.object(current_account.minimum_single_withdrawal_limit, "validate")
    @patch.object(current_account.minimum_single_deposit_limit, "validate")
    @patch.object(current_account.overdraft_limit, "validate")
    @patch.object(current_account.utils, "validate_denomination")
    @patch.object(current_account.utils, "get_parameter")
    @patch.object(current_account.utils, "is_flag_in_list_applied")
    @patch.object(current_account.utils, "is_force_override")
    def test_rejects_postings_when_daily_deposit_limit_is_surpassed(
        self,
        mock_is_force_override: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_overdraft_limit: MagicMock,
        mock_validate_minimum_single_deposit_limit: MagicMock,
        mock_validate_minimum_single_withdrawal_limit: MagicMock,
        mock_validate_maximum_balance_limit: MagicMock,
        mock_available_balance_validate: MagicMock,
        mock_validate_maximum_daily_withdrawal_limit: MagicMock,
        mock_validate_maximum_daily_deposit_limit: MagicMock,
    ):
        postings = [SentinelCustomInstruction("dummy_posting")]
        rejection = SentinelRejection("dummy_rejection")

        # setup mocks
        mock_is_force_override.return_value = False
        mock_is_flag_in_list_applied.return_value = False
        mock_validate_denomination.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": "GBP",
                "additional_denominations": [],
            }
        )
        mock_validate_overdraft_limit.return_value = None
        mock_validate_minimum_single_deposit_limit.return_value = None
        mock_validate_minimum_single_withdrawal_limit.return_value = None
        mock_validate_maximum_balance_limit.return_value = None
        mock_available_balance_validate.return_value = None
        mock_validate_maximum_daily_withdrawal_limit.return_value = None
        mock_validate_maximum_daily_deposit_limit.return_value = rejection

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                "live_balances_bof": SentinelBalancesObservation("dummy_observation")
            },
            client_transactions_mapping={
                "EFFECTIVE_DATE_POSTINGS_FETCHER": sentinel.effective_date_transactions
            },
        )

        # hook call
        hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATE,
            posting_instructions=postings,
            client_transactions=sentinel.proposed_client_transactions,
        )
        hook_result = current_account.pre_posting_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )

        # assertions
        self.assertEqual(hook_result, PrePostingHookResult(rejection=rejection))
        mock_validate_maximum_daily_deposit_limit.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_arguments,
            denomination=self.default_denomination,
            effective_date_client_transactions=sentinel.effective_date_transactions,
        )

    @patch.object(current_account.maximum_daily_withdrawal_by_transaction_type, "validate")
    @patch.object(current_account.maximum_daily_deposit_limit, "validate")
    @patch.object(current_account.maximum_daily_withdrawal, "validate")
    @patch.object(current_account.available_balance, "validate")
    @patch.object(current_account.maximum_balance_limit, "validate")
    @patch.object(current_account.minimum_single_withdrawal_limit, "validate")
    @patch.object(current_account.minimum_single_deposit_limit, "validate")
    @patch.object(current_account.overdraft_limit, "validate")
    @patch.object(current_account.utils, "validate_denomination")
    @patch.object(current_account.utils, "get_parameter")
    @patch.object(current_account.utils, "is_flag_in_list_applied")
    @patch.object(current_account.utils, "is_force_override")
    def test_accept_posting_instructions_when_not_dormant_and_within_limits(
        self,
        mock_is_force_override: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_overdraft_limit: MagicMock,
        mock_validate_minimum_single_deposit_limit: MagicMock,
        mock_validate_minimum_single_withdrawal_limit: MagicMock,
        mock_validate_maximum_balance_limit: MagicMock,
        mock_available_balance_validate: MagicMock,
        mock_validate_maximum_daily_withdrawal: MagicMock,
        mock_validate_maximum_daily_deposit_limit: MagicMock,
        mock_validate_maximum_daily_atm_withdrawal_limit: MagicMock,
    ):
        postings = [SentinelCustomInstruction("dummy_posting")]

        # setup mocks
        mock_is_force_override.return_value = False
        mock_is_flag_in_list_applied.return_value = False
        mock_validate_denomination.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP", "additional_denominations": []}
        )
        mock_validate_overdraft_limit.return_value = None
        mock_validate_minimum_single_deposit_limit.return_value = None
        mock_validate_minimum_single_withdrawal_limit.return_value = None
        mock_validate_maximum_balance_limit.return_value = None
        mock_validate_maximum_daily_deposit_limit.return_value = None
        mock_validate_maximum_daily_withdrawal.return_value = None
        mock_available_balance_validate.return_value = None
        mock_validate_maximum_daily_atm_withdrawal_limit.return_value = None

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                "live_balances_bof": SentinelBalancesObservation("dummy_observation")
            },
            client_transactions_mapping={
                "EFFECTIVE_DATE_POSTINGS_FETCHER": sentinel.effective_date_transactions
            },
        )

        # hook call
        hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATE, posting_instructions=postings, client_transactions={}
        )
        hook_result = current_account.pre_posting_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )

        # assertions
        self.assertIsNone(hook_result)
        mock_is_force_override.assert_called_once_with(posting_instructions=postings)
        mock_is_flag_in_list_applied.assert_called_once_with(
            vault=mock_vault, parameter_name="dormancy_flags", effective_datetime=DEFAULT_DATE
        )
        mock_get_parameter.assert_has_calls(
            [
                call(vault=mock_vault, name="denomination", at_datetime=DEFAULT_DATE),
                call(vault=mock_vault, name="additional_denominations", is_json=True),
            ]
        )
        mock_validate_denomination.assert_called_once_with(
            posting_instructions=postings, accepted_denominations=[self.default_denomination]
        )
        mock_validate_overdraft_limit.assert_called_once_with(
            vault=mock_vault,
            postings=postings,
            denomination=self.default_denomination,
            balances=sentinel.balances_dummy_observation,
        )
        mock_validate_minimum_single_deposit_limit.assert_called_once_with(
            vault=mock_vault,
            postings=postings,
            denomination=self.default_denomination,
        )
        mock_validate_minimum_single_withdrawal_limit.assert_called_once_with(
            vault=mock_vault,
            postings=postings,
            denomination=self.default_denomination,
        )
        mock_validate_maximum_balance_limit.assert_called_once_with(
            vault=mock_vault,
            postings=postings,
            denomination=self.default_denomination,
            balances=sentinel.balances_dummy_observation,
        )
        mock_validate_maximum_daily_withdrawal.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_arguments,
            denomination=self.default_denomination,
            effective_date_client_transactions=sentinel.effective_date_transactions,
        )
        mock_validate_maximum_daily_deposit_limit.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_arguments,
            denomination=self.default_denomination,
            effective_date_client_transactions=sentinel.effective_date_transactions,
        )

    @patch.object(current_account.maximum_daily_withdrawal_by_transaction_type, "validate")
    @patch.object(current_account.maximum_daily_deposit_limit, "validate")
    @patch.object(current_account.maximum_daily_withdrawal, "validate")
    @patch.object(current_account.available_balance, "validate")
    @patch.object(current_account.maximum_balance_limit, "validate")
    @patch.object(current_account.minimum_single_withdrawal_limit, "validate")
    @patch.object(current_account.minimum_single_deposit_limit, "validate")
    @patch.object(current_account.overdraft_limit, "validate")
    @patch.object(current_account.utils, "validate_denomination")
    @patch.object(current_account.utils, "get_parameter")
    @patch.object(current_account.utils, "is_flag_in_list_applied")
    @patch.object(current_account.utils, "is_force_override")
    def test_rejects_withdrawal_when_maximum_daily_atm_limit_is_surpassed(
        self,
        mock_is_force_override: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_overdraft_limit: MagicMock,
        mock_validate_minimum_single_deposit_limit: MagicMock,
        mock_validate_minimum_single_withdrawal_limit: MagicMock,
        mock_validate_maximum_balance_limit: MagicMock,
        mock_validate_available_balance: MagicMock,
        mock_validate_maximum_daily_withdrawal: MagicMock,
        mock_validate_maximum_daily_deposit_limit: MagicMock,
        mock_validate_maximum_daily_atm_withdrawal_limit: MagicMock,
    ):
        rejection = SentinelRejection("dummy_rejection")

        # setup mocks
        mock_is_force_override.return_value = False
        mock_is_flag_in_list_applied.return_value = False
        mock_validate_denomination.return_value = None
        mock_validate_available_balance.return_value = None
        mock_validate_maximum_daily_withdrawal.return_value = None
        mock_validate_maximum_daily_deposit_limit.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP", "additional_denominations": []}
        )
        mock_validate_overdraft_limit.return_value = None
        mock_validate_minimum_single_deposit_limit.return_value = None
        mock_validate_minimum_single_withdrawal_limit.return_value = None
        mock_validate_maximum_balance_limit.return_value = None
        mock_validate_maximum_daily_atm_withdrawal_limit.return_value = rejection
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                "live_balances_bof": SentinelBalancesObservation("dummy_observation")
            },
            client_transactions_mapping={
                "EFFECTIVE_DATE_POSTINGS_FETCHER": sentinel.current_ctx,
            },
        )

        # hook call
        hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATE,
            posting_instructions=sentinel.posting_instructions,
            client_transactions=sentinel.proposed_ctx,
        )
        hook_result = current_account.pre_posting_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )

        # assertions
        self.assertEqual(hook_result, PrePostingHookResult(rejection=rejection))
        mock_validate_maximum_daily_atm_withdrawal_limit.assert_called_once_with(
            vault=mock_vault,
            denomination=self.default_denomination,
            hook_arguments=hook_arguments,
            effective_date_client_transactions=sentinel.current_ctx,
        )
