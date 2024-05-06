# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
import library.time_deposit.contracts.template.time_deposit as time_deposit
from library.time_deposit.test.unit.test_time_deposit_common import TimeDepositTest

# contracts api
from contracts_api import PostParameterChangeHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PostParameterChangeHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelUpdateAccountEventTypeDirective,
)


class RenewedTimeDepositPostParameterChangeHookTest(TimeDepositTest):
    def test_term_not_in_updated_parameters_returns_none(self):
        hook_args = PostParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            old_parameter_values={sentinel.parameter: sentinel.old_value},
            updated_parameter_values={sentinel.parameter: sentinel.updated_value},
        )
        self.assertIsNone(
            time_deposit.post_parameter_change_hook(vault=sentinel.vault, hook_arguments=hook_args)
        )

    @patch.object(time_deposit.deposit_maturity, "handle_term_parameter_change")
    def test_term_in_updated_parameters_returns_updated_maturity_schedule(
        self, mock_handle_term_parameter_change: MagicMock
    ):
        mock_handle_term_parameter_change.return_value = [
            SentinelUpdateAccountEventTypeDirective("account_maturity"),
            SentinelUpdateAccountEventTypeDirective("notify_upcoming_maturity"),
        ]

        hook_args = PostParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            old_parameter_values={time_deposit.deposit_parameters.PARAM_TERM: sentinel.old_value},
            updated_parameter_values={
                time_deposit.deposit_parameters.PARAM_TERM: sentinel.updated_value
            },
        )

        expected_result = PostParameterChangeHookResult(
            update_account_event_type_directives=[
                SentinelUpdateAccountEventTypeDirective("account_maturity"),
                SentinelUpdateAccountEventTypeDirective("notify_upcoming_maturity"),
            ]
        )
        self.assertEqual(
            time_deposit.post_parameter_change_hook(vault=sentinel.vault, hook_arguments=hook_args),
            expected_result,
        )
