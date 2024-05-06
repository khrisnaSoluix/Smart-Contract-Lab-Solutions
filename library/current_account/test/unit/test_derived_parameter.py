# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
from library.current_account.test.unit.current_account_common import (
    DEFAULT_DATE,
    CurrentAccountTest,
    current_account,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DerivedParameterHookArguments,
    DerivedParameterHookResult,
)


class DerivedParameterHookTest(CurrentAccountTest):
    @patch.object(current_account.account_tiers, "get_account_tier")
    def test_derived_parameters_hook(
        self,
        mock_get_account_tier: MagicMock,
    ):
        mock_get_account_tier.return_value = sentinel.tier_name
        hook_arguments = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATE)
        hook_result = current_account.derived_parameter_hook(sentinel.vault, hook_arguments)
        expected_result = DerivedParameterHookResult(
            parameters_return_value={current_account.PARAM_ACCOUNT_TIER_NAME: sentinel.tier_name}
        )
        self.assertEqual(hook_result, expected_result)
        mock_get_account_tier.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATE
        )
