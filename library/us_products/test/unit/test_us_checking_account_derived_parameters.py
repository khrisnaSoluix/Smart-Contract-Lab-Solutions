# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
from library.us_products.contracts.template import us_checking_account
from library.us_products.test.unit.test_us_checking_account_common import CheckingAccountTest

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DerivedParameterHookArguments,
    DerivedParameterHookResult,
)


class DerivedParameterHookTest(CheckingAccountTest):
    @patch.object(us_checking_account.account_tiers, "get_account_tier")
    def test_derived_parameters_hook(
        self,
        mock_get_account_tier: MagicMock,
    ):
        # setup mocks
        mock_get_account_tier.return_value = sentinel.tier_name

        # hook call
        hook_arguments = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)
        hook_result = us_checking_account.derived_parameter_hook(sentinel.vault, hook_arguments)

        # expected result
        expected_result = DerivedParameterHookResult(
            parameters_return_value={
                us_checking_account.PARAM_ACTIVE_ACCOUNT_TIER_NAME: sentinel.tier_name
            }
        )

        # assertions
        self.assertEqual(hook_result, expected_result)
        mock_get_account_tier.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME
        )
