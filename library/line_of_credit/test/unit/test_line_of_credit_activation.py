# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
from library.line_of_credit.contracts.template import line_of_credit
from library.line_of_credit.test.unit.test_line_of_credit_common import (
    DEFAULT_DATETIME,
    LineOfCreditTestBase,
)

# contracts api
from contracts_api import ActivationHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    ActivationHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelScheduledEvent,
)


@patch.object(line_of_credit.utils, "get_parameter")
@patch.object(line_of_credit.due_amount_calculation, "scheduled_events")
class LineOfCreditActivationTest(LineOfCreditTestBase):
    common_param_return_values = {
        line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_HOUR: "0",
        line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_MINUTE: "0",
        line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_SECOND: "2",
    }

    def test_activation_hook(
        self,
        mock_due_amount_scheduled_events: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        due_amount_calculation_scheduled_event = {
            sentinel.due_amount: SentinelScheduledEvent("due_amount_event")
        }
        mock_due_amount_scheduled_events.return_value = due_amount_calculation_scheduled_event

        expected = ActivationHookResult(
            scheduled_events_return_value={**due_amount_calculation_scheduled_event}
        )

        # run hook
        hook_args = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = line_of_credit.activation_hook(vault=sentinel.vault, hook_arguments=hook_args)

        # validate result
        self.assertEqual(result, expected)
        mock_due_amount_scheduled_events.assert_called_once_with(
            vault=sentinel.vault, account_opening_datetime=DEFAULT_DATETIME
        )
