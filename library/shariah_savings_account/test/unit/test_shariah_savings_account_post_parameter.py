# standard libs
from unittest.mock import Mock, patch, sentinel

# library
import library.shariah_savings_account.contracts.template.shariah_savings_account as shariah_savings_account  # noqa: E501
from library.shariah_savings_account.test.unit.test_shariah_savings_account_common import (  # noqa: E501
    ShariahSavingsAccountTestBase,
)

# contracts api
from contracts_api import PostParameterChangeHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PostParameterChangeHookResult,
    ScheduledEvent,
    UpdateAccountEventTypeDirective,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelEndOfMonthSchedule,
)


class PostParameterChangeHookTest(ShariahSavingsAccountTestBase):
    @patch.object(shariah_savings_account.utils, "has_parameter_value_changed")
    def test_post_parameter_change_hook_no_param_changed(
        self, mock_has_parameter_value_changed: Mock
    ):
        mock_vault = self.create_mock()
        mock_has_parameter_value_changed.return_value = False

        hook_arguments = PostParameterChangeHookArguments(
            old_parameter_values=sentinel.old_parameter_values,
            updated_parameter_values=sentinel.new_parameter_values,
            effective_datetime=DEFAULT_DATETIME,
        )
        hook_result = shariah_savings_account.post_parameter_change_hook(mock_vault, hook_arguments)
        self.assertIsNone(hook_result)

        # Assert calls
        mock_has_parameter_value_changed.assert_called_with(
            parameter_name="profit_application_day",
            old_parameters=sentinel.old_parameter_values,
            updated_parameters=sentinel.new_parameter_values,
        )

    @patch.object(shariah_savings_account.profit_application, "scheduled_events")
    @patch.object(shariah_savings_account.utils, "has_parameter_value_changed")
    def test_post_parameter_change_hook_with_param_updated(
        self,
        mock_has_parameter_value_changed: Mock,
        mock_scheduled_events: Mock,
    ):
        mock_vault = self.create_mock()
        mock_has_parameter_value_changed.return_value = True

        mock_method = SentinelEndOfMonthSchedule("monthly_schedule")
        mock_scheduled_events.return_value = {
            "APPLY_PROFIT": ScheduledEvent(
                start_datetime=DEFAULT_DATETIME,
                schedule_method=mock_method,
            )
        }

        expected_result = PostParameterChangeHookResult(
            update_account_event_type_directives=[
                UpdateAccountEventTypeDirective(
                    event_type="APPLY_PROFIT",
                    schedule_method=mock_method,
                )
            ]
        )

        hook_arguments = PostParameterChangeHookArguments(
            old_parameter_values=sentinel.old_parameter_values,
            updated_parameter_values=sentinel.new_parameter_values,
            effective_datetime=DEFAULT_DATETIME,
        )

        hook_result = shariah_savings_account.post_parameter_change_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )
        self.assertEqual(expected_result, hook_result)

        # Assert calls
        mock_has_parameter_value_changed.assert_called_with(
            parameter_name="profit_application_day",
            old_parameters=sentinel.old_parameter_values,
            updated_parameters=sentinel.new_parameter_values,
        )
        mock_scheduled_events.assert_called_with(
            vault=mock_vault,
            start_datetime=hook_arguments.effective_datetime,
        )
