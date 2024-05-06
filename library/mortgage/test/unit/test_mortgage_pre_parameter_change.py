# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
import library.mortgage.contracts.template.mortgage as mortgage
from library.mortgage.test.unit.test_mortgage_common import MortgageTestBase

# contracts api
from contracts_api import PreParameterChangeHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PreParameterChangeHookResult,
    Rejection,
    RejectionReason,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelRejection,
)


@patch.object(mortgage.due_amount_calculation, "validate_due_amount_calculation_day_change")
@patch.object(mortgage.repayment_holiday, "is_due_amount_calculation_blocked")
class PreParameterChangeHookTest(MortgageTestBase):
    def test_no_rejections_raised_returns_none(
        self,
        mock_is_due_amount_calculation_blocked: MagicMock,
        mock_validate_due_amount_calculation_day_change: MagicMock,
    ):
        # construct mocks
        mock_is_due_amount_calculation_blocked.return_value = False
        mock_validate_due_amount_calculation_day_change.return_value = None

        # run function
        hook_args = PreParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            updated_parameter_values={
                mortgage.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: sentinel.param
            },
        )
        result = mortgage.pre_parameter_change_hook(vault=sentinel.vault, hook_arguments=hook_args)
        self.assertIsNone(result)

    def test_rejects_day_change_before_first_execution_datetime(
        self,
        mock_is_due_amount_calculation_blocked: MagicMock,
        mock_validate_due_amount_calculation_day_change: MagicMock,
    ):
        # construct mocks
        mock_is_due_amount_calculation_blocked.return_value = False
        due_amount_day_rejection = SentinelRejection("rejection")
        mock_validate_due_amount_calculation_day_change.return_value = due_amount_day_rejection

        # construct expected result
        expected_result = PreParameterChangeHookResult(rejection=due_amount_day_rejection)

        # run function
        hook_args = PreParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            updated_parameter_values={
                mortgage.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: sentinel.param
            },
        )
        result = mortgage.pre_parameter_change_hook(vault=sentinel.vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)

    def test_rejects_day_change_during_repayment_holiday(
        self,
        mock_is_due_amount_calculation_blocked: MagicMock,
        mock_validate_due_amount_calculation_day_change: MagicMock,
    ):
        # construct mocks
        mock_is_due_amount_calculation_blocked.return_value = True

        # construct expected result
        expected_result = PreParameterChangeHookResult(
            rejection=Rejection(
                message="The due_amount_calculation_day parameter cannot be updated during a "
                "repayment holiday.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )

        # run function
        hook_args = PreParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            updated_parameter_values={
                mortgage.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: sentinel.param
            },
        )
        result = mortgage.pre_parameter_change_hook(vault=sentinel.vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)

        mock_validate_due_amount_calculation_day_change.assert_not_called()
