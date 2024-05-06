# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
from library.savings_account.test.unit.savings_account_common import (
    DEFAULT_DATE,
    SavingsAccountTest,
    savings_account,
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


class PrePostingHookTest(SavingsAccountTest):
    @patch.object(savings_account.utils, "is_force_override")
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
        hook_result = savings_account.pre_posting_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )

        # assertions
        self.assertIsNone(hook_result)
        mock_is_force_override.assert_called_once_with(posting_instructions=postings)

    @patch.object(savings_account.utils, "is_flag_in_list_applied")
    @patch.object(savings_account.utils, "is_force_override")
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
        hook_result = savings_account.pre_posting_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )

        # assertions
        mock_is_flag_in_list_applied.assert_called_once_with(
            vault=mock_vault, parameter_name="dormancy_flags", effective_datetime=DEFAULT_DATE
        )
        self.assertEqual(hook_result, expected_result)

    @patch.object(savings_account.utils, "validate_denomination")
    @patch.object(savings_account.utils, "get_parameter")
    @patch.object(savings_account.utils, "is_flag_in_list_applied")
    @patch.object(savings_account.utils, "is_force_override")
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
            parameters={"denomination": "GBP"}
        )
        mock_validate_denomination.return_value = rejection
        mock_vault = sentinel.vault

        # hook call
        hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATE, posting_instructions=postings, client_transactions={}
        )
        hook_result = savings_account.pre_posting_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )

        # assertions
        self.assertEqual(hook_result, PrePostingHookResult(rejection=rejection))
        mock_get_parameter.assert_called_once_with(
            vault=mock_vault, name="denomination", at_datetime=DEFAULT_DATE
        )
        mock_validate_denomination.assert_called_once_with(
            posting_instructions=postings, accepted_denominations=["GBP"]
        )

    @patch.object(savings_account.available_balance, "validate")
    @patch.object(savings_account.utils, "validate_denomination")
    @patch.object(savings_account.utils, "get_parameter")
    @patch.object(savings_account.utils, "is_flag_in_list_applied")
    @patch.object(savings_account.utils, "is_force_override")
    def test_rejects_postings_when_balance_is_surpassed_for_the_denomination(
        self,
        mock_is_force_override: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_available_balance: MagicMock,
    ):
        postings = [SentinelCustomInstruction("dummy_posting")]
        rejection = SentinelRejection("dummy_rejection")

        # setup mocks
        mock_is_force_override.return_value = False
        mock_is_flag_in_list_applied.return_value = False
        mock_validate_denomination.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP"}
        )
        mock_validate_available_balance.return_value = rejection

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                "live_balances_bof": SentinelBalancesObservation("dummy_observation")
            }
        )

        # hook call
        hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATE, posting_instructions=postings, client_transactions={}
        )
        hook_result = savings_account.pre_posting_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )

        # assertions
        self.assertEqual(hook_result, PrePostingHookResult(rejection=rejection))
        mock_validate_available_balance.assert_called_once_with(
            balances=sentinel.balances_dummy_observation,
            denominations=["GBP"],
            posting_instructions=postings,
        )

    @patch.object(savings_account.available_balance, "validate")
    @patch.object(savings_account.minimum_single_deposit_limit, "validate")
    @patch.object(savings_account.utils, "validate_denomination")
    @patch.object(savings_account.utils, "get_parameter")
    @patch.object(savings_account.utils, "is_flag_in_list_applied")
    @patch.object(savings_account.utils, "is_force_override")
    def test_rejects_postings_when_minimum_single_deposit_is_not_met(
        self,
        mock_is_force_override: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_minimum_single_deposit_limit: MagicMock,
        mock_validate_available_balance: MagicMock,
    ):
        postings = [SentinelCustomInstruction("dummy_posting")]
        rejection = SentinelRejection("dummy_rejection")

        # setup mocks
        mock_is_force_override.return_value = False
        mock_is_flag_in_list_applied.return_value = False
        mock_validate_denomination.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP"}
        )
        mock_validate_available_balance.return_value = None
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
        hook_result = savings_account.pre_posting_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )

        # assertions
        self.assertEqual(hook_result, PrePostingHookResult(rejection=rejection))
        mock_validate_minimum_single_deposit_limit.assert_called_once_with(
            vault=mock_vault,
            postings=postings,
            denomination=self.default_denomination,
        )

    @patch.object(savings_account.minimum_single_withdrawal_limit, "validate")
    @patch.object(savings_account.minimum_single_deposit_limit, "validate")
    @patch.object(savings_account.available_balance, "validate")
    @patch.object(savings_account.utils, "validate_denomination")
    @patch.object(savings_account.utils, "get_parameter")
    @patch.object(savings_account.utils, "is_flag_in_list_applied")
    @patch.object(savings_account.utils, "is_force_override")
    def test_rejects_postings_when_minimum_single_withdrawal_is_not_met(
        self,
        mock_is_force_override: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_available_balance: MagicMock,
        mock_validate_minimum_single_deposit_limit: MagicMock,
        mock_validate_minimum_single_withdrawal_limit: MagicMock,
    ):
        postings = [SentinelCustomInstruction("dummy_posting")]
        rejection = SentinelRejection("dummy_rejection")

        # setup mocks
        mock_is_force_override.return_value = False
        mock_is_flag_in_list_applied.return_value = False
        mock_validate_denomination.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP"}
        )
        mock_validate_available_balance.return_value = None
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
        hook_result = savings_account.pre_posting_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )

        # assertions
        self.assertEqual(hook_result, PrePostingHookResult(rejection=rejection))
        mock_validate_minimum_single_withdrawal_limit.assert_called_once_with(
            vault=mock_vault,
            postings=postings,
            denomination=self.default_denomination,
        )

    @patch.object(savings_account.maximum_balance_limit, "validate")
    @patch.object(savings_account.minimum_single_withdrawal_limit, "validate")
    @patch.object(savings_account.minimum_single_deposit_limit, "validate")
    @patch.object(savings_account.available_balance, "validate")
    @patch.object(savings_account.utils, "validate_denomination")
    @patch.object(savings_account.utils, "get_parameter")
    @patch.object(savings_account.utils, "is_flag_in_list_applied")
    @patch.object(savings_account.utils, "is_force_override")
    def test_rejects_postings_when_maximum_balance_is_surpassed(
        self,
        mock_is_force_override: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_available_balance: MagicMock,
        mock_validate_minimum_single_deposit_limit: MagicMock,
        mock_validate_minimum_single_withdrawal_limit: MagicMock,
        mock_validate_maximum_balance_limit: MagicMock,
    ):
        postings = [SentinelCustomInstruction("dummy_posting")]
        rejection = SentinelRejection("dummy_rejection")

        # setup mocks
        mock_is_force_override.return_value = False
        mock_is_flag_in_list_applied.return_value = False
        mock_validate_denomination.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP"}
        )
        mock_validate_available_balance.return_value = None
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
        hook_result = savings_account.pre_posting_hook(
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

    @patch.object(savings_account.maximum_daily_withdrawal, "validate")
    @patch.object(savings_account.maximum_balance_limit, "validate")
    @patch.object(savings_account.minimum_single_withdrawal_limit, "validate")
    @patch.object(savings_account.minimum_single_deposit_limit, "validate")
    @patch.object(savings_account.available_balance, "validate")
    @patch.object(savings_account.utils, "validate_denomination")
    @patch.object(savings_account.utils, "get_parameter")
    @patch.object(savings_account.utils, "is_flag_in_list_applied")
    @patch.object(savings_account.utils, "is_force_override")
    def test_rejects_postings_when_maximum_daily_withdrawal_limit_is_surpassed(
        self,
        mock_is_force_override: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_available_balance: MagicMock,
        mock_validate_minimum_single_deposit_limit: MagicMock,
        mock_validate_minimum_single_withdrawal_limit: MagicMock,
        mock_validate_maximum_balance_limit: MagicMock,
        mock_validate_maximum_daily_withdrawal: MagicMock,
    ):
        postings = [SentinelCustomInstruction("dummy_posting")]
        rejection = SentinelRejection("dummy_rejection")

        # setup mocks
        mock_is_force_override.return_value = False
        mock_is_flag_in_list_applied.return_value = False
        mock_validate_denomination.return_value = None
        mock_validate_minimum_single_deposit_limit.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP"}
        )
        mock_validate_available_balance.return_value = None
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
        hook_result = savings_account.pre_posting_hook(
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

    @patch.object(savings_account.maximum_daily_deposit_limit, "validate")
    @patch.object(savings_account.maximum_daily_withdrawal, "validate")
    @patch.object(savings_account.maximum_balance_limit, "validate")
    @patch.object(savings_account.minimum_single_withdrawal_limit, "validate")
    @patch.object(savings_account.minimum_single_deposit_limit, "validate")
    @patch.object(savings_account.available_balance, "validate")
    @patch.object(savings_account.utils, "validate_denomination")
    @patch.object(savings_account.utils, "get_parameter")
    @patch.object(savings_account.utils, "is_flag_in_list_applied")
    @patch.object(savings_account.utils, "is_force_override")
    def test_rejects_postings_when_daily_deposit_limit_is_surpassed(
        self,
        mock_is_force_override: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_available_balance: MagicMock,
        mock_validate_minimum_single_deposit_limit: MagicMock,
        mock_validate_minimum_single_withdrawal_limit: MagicMock,
        mock_validate_maximum_balance_limit: MagicMock,
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
            parameters={"denomination": "GBP"}
        )
        mock_validate_available_balance.return_value = None
        mock_validate_minimum_single_deposit_limit.return_value = None
        mock_validate_minimum_single_withdrawal_limit.return_value = None
        mock_validate_maximum_balance_limit.return_value = None
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
        hook_result = savings_account.pre_posting_hook(
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

    @patch.object(savings_account.maximum_daily_withdrawal_by_transaction_type, "validate")
    @patch.object(savings_account.maximum_daily_deposit_limit, "validate")
    @patch.object(savings_account.maximum_daily_withdrawal, "validate")
    @patch.object(savings_account.available_balance, "validate")
    @patch.object(savings_account.maximum_balance_limit, "validate")
    @patch.object(savings_account.minimum_single_withdrawal_limit, "validate")
    @patch.object(savings_account.minimum_single_deposit_limit, "validate")
    @patch.object(savings_account.utils, "validate_denomination")
    @patch.object(savings_account.utils, "get_parameter")
    @patch.object(savings_account.utils, "is_flag_in_list_applied")
    @patch.object(savings_account.utils, "is_force_override")
    def test_rejects_withdrawal_when_maximum_daily_atm_limit_is_surpassed(
        self,
        mock_is_force_override: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_validate_denomination: MagicMock,
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
            parameters={"denomination": "GBP"}
        )
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
        hook_result = savings_account.pre_posting_hook(
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

    @patch.object(savings_account.maximum_daily_withdrawal_by_transaction_type, "validate")
    @patch.object(savings_account.maximum_daily_deposit_limit, "validate")
    @patch.object(savings_account.maximum_daily_withdrawal, "validate")
    @patch.object(savings_account.available_balance, "validate")
    @patch.object(savings_account.maximum_balance_limit, "validate")
    @patch.object(savings_account.minimum_single_withdrawal_limit, "validate")
    @patch.object(savings_account.minimum_single_deposit_limit, "validate")
    @patch.object(savings_account.utils, "validate_denomination")
    @patch.object(savings_account.utils, "get_parameter")
    @patch.object(savings_account.utils, "is_flag_in_list_applied")
    @patch.object(savings_account.utils, "is_force_override")
    def test_accept_posting_instructions_when_not_dormant_and_within_limits(
        self,
        mock_is_force_override: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_minimum_single_deposit_limit: MagicMock,
        mock_validate_minimum_single_withdrawal_limit: MagicMock,
        mock_validate_maximum_balance_limit: MagicMock,
        mock_validate_available_balance: MagicMock,
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
            parameters={"denomination": "GBP"}
        )
        mock_validate_available_balance.return_value = None
        mock_validate_minimum_single_deposit_limit.return_value = None
        mock_validate_minimum_single_withdrawal_limit.return_value = None
        mock_validate_maximum_balance_limit.return_value = None
        mock_validate_maximum_daily_deposit_limit.return_value = None
        mock_validate_maximum_daily_withdrawal.return_value = None
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
        hook_result = savings_account.pre_posting_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )

        # assertions
        self.assertIsNone(hook_result)
        mock_is_force_override.assert_called_once_with(posting_instructions=postings)
        mock_is_flag_in_list_applied.assert_called_once_with(
            vault=mock_vault, parameter_name="dormancy_flags", effective_datetime=DEFAULT_DATE
        )
        mock_get_parameter.assert_called_once_with(
            vault=mock_vault, name="denomination", at_datetime=DEFAULT_DATE
        )
        mock_validate_denomination.assert_called_once_with(
            posting_instructions=postings, accepted_denominations=[self.default_denomination]
        )
        mock_validate_available_balance.assert_called_once_with(
            balances=sentinel.balances_dummy_observation,
            denominations=["GBP"],
            posting_instructions=postings,
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
