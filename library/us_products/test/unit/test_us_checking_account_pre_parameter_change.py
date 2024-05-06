# standard libs
from json import dumps
from unittest.mock import MagicMock, patch, sentinel

# library
from library.us_products.test.unit.test_us_checking_account_common import (
    DEFAULT_DATE,
    CheckingAccountTest,
    us_checking_account,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PreParameterChangeHookArguments,
    PreParameterChangeHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelRejection,
)

feature_daily_transaction_withdrawal = (
    us_checking_account.maximum_daily_withdrawal_by_transaction_type
)  # noqa: E501


@patch.object(
    us_checking_account.maximum_daily_withdrawal_by_transaction_type, "validate_parameter_change"
)
class PreParameterChangeHookTest(CheckingAccountTest):
    def test_unknown_parameter_update_returns_none(self, mock_validate_parameter_change: MagicMock):
        # hook call
        hook_arguments = PreParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATE,
            updated_parameter_values={sentinel.parameter: sentinel.value},
        )
        hook_result = us_checking_account.pre_parameter_change_hook(
            vault=sentinel.vault, hook_arguments=hook_arguments
        )
        # assertions
        self.assertIsNone(hook_result)
        mock_validate_parameter_change.assert_not_called()

    def test_daily_withdrawal_limit_parameter_update_is_rejected(
        self, mock_validate_parameter_change: MagicMock
    ):
        # mocks
        mock_validate_parameter_change.return_value = SentinelRejection("dummy_rejection")
        mock_vault = sentinel.vault
        # hook call
        hook_arguments = PreParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATE,
            updated_parameter_values={
                feature_daily_transaction_withdrawal.PARAM_DAILY_WITHDRAWAL_LIMIT_BY_TRANSACTION: dumps(  # noqa: E501
                    {"ATM": "2000"}
                )
            },
        )
        hook_result = us_checking_account.pre_parameter_change_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )
        # assertions
        self.assertEqual(
            hook_result,
            PreParameterChangeHookResult(rejection=SentinelRejection("dummy_rejection")),
        )
        mock_validate_parameter_change.assert_called_once_with(
            vault=mock_vault, proposed_parameter_value=dumps({"ATM": "2000"})
        )

    def test_daily_withdrawal_limit_parameter_update_is_accepted_returns_none(
        self, mock_validate_parameter_change: MagicMock
    ):
        # mocks
        mock_validate_parameter_change.return_value = None
        mock_vault = sentinel.vault
        # hook call
        hook_arguments = PreParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATE,
            updated_parameter_values={
                feature_daily_transaction_withdrawal.PARAM_DAILY_WITHDRAWAL_LIMIT_BY_TRANSACTION: dumps(  # noqa: E501
                    {"ATM": "2000"}
                )
            },
        )
        hook_result = us_checking_account.pre_parameter_change_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )
        # assertions
        self.assertIsNone(hook_result)
