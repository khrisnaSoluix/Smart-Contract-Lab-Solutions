# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
from library.loan.contracts.template import loan
from library.loan.test.unit.test_loan_common import LoanTestBase

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

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


class PreParameterChangeHookTest(LoanTestBase):
    def test_no_due_amount_calculation_day_parameter_change_returns_none(
        self,
    ):
        # run function
        hook_args = PreParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            updated_parameter_values={},
        )
        result = loan.pre_parameter_change_hook(vault=sentinel.vault, hook_arguments=hook_args)

        self.assertIsNone(result)

    @patch.object(loan.due_amount_calculation, "validate_due_amount_calculation_day_change")
    @patch.object(loan.utils, "get_parameter")
    def test_rejects_day_change_before_first_execution_datetime(
        self,
        mock_get_parameter: MagicMock,
        mock_validate_due_amount_calculation_day_change: MagicMock,
    ):
        # expected values
        due_amount_day_rejection = SentinelRejection("rejection")

        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"amortisation_method": "declining_principal"}
        )
        mock_validate_due_amount_calculation_day_change.return_value = due_amount_day_rejection

        # construct expected result
        expected_result = PreParameterChangeHookResult(rejection=due_amount_day_rejection)

        # run function
        hook_args = PreParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            updated_parameter_values={
                loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: sentinel.param
            },
        )
        result = loan.pre_parameter_change_hook(vault=sentinel.vault, hook_arguments=hook_args)

        self.assertEqual(result, expected_result)
        mock_validate_due_amount_calculation_day_change.assert_called_once_with(
            vault=sentinel.vault
        )

    @patch.object(loan.due_amount_calculation, "validate_due_amount_calculation_day_change")
    @patch.object(loan.repayment_holiday, "is_due_amount_calculation_blocked")
    @patch.object(loan.utils, "get_parameter")
    def test_rejects_day_change_if_active_due_amount_blocking_flags(
        self,
        mock_get_parameter: MagicMock,
        mock_is_due_amount_calculation_blocked: MagicMock,
        mock_validate_due_amount_calculation_day_change: MagicMock,
    ):
        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"amortisation_method": "declining_principal"}
        )
        mock_validate_due_amount_calculation_day_change.return_value = None
        mock_is_due_amount_calculation_blocked.return_value = True

        # construct expected result
        expected_result = PreParameterChangeHookResult(
            rejection=Rejection(
                message=(
                    "It is not possible to change the due amount calculation day if "
                    "there are active due amount blocking flags."
                ),
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )

        # run function
        hook_args = PreParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            updated_parameter_values={
                loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: sentinel.param
            },
        )
        result = loan.pre_parameter_change_hook(vault=sentinel.vault, hook_arguments=hook_args)

        self.assertEqual(result, expected_result)
        mock_validate_due_amount_calculation_day_change.assert_called_once_with(
            vault=sentinel.vault
        )
        mock_is_due_amount_calculation_blocked.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME
        )

    @patch.object(loan.due_amount_calculation, "validate_due_amount_calculation_day_change")
    @patch.object(loan.repayment_holiday, "is_due_amount_calculation_blocked")
    @patch.object(loan.utils, "get_parameter")
    def test_no_rejections_raised_returns_none(
        self,
        mock_get_parameter: MagicMock,
        mock_is_due_amount_calculation_blocked: MagicMock,
        mock_validate_due_amount_calculation_day_change: MagicMock,
    ):
        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"amortisation_method": "declining_principal"}
        )
        mock_validate_due_amount_calculation_day_change.return_value = None
        mock_is_due_amount_calculation_blocked.return_value = None

        # run function
        hook_args = PreParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            updated_parameter_values={
                loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: sentinel.param
            },
        )
        result = loan.pre_parameter_change_hook(vault=sentinel.vault, hook_arguments=hook_args)

        self.assertIsNone(result)
        mock_validate_due_amount_calculation_day_change.assert_called_once_with(
            vault=sentinel.vault
        )
        mock_is_due_amount_calculation_blocked.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME
        )

    @patch.object(loan.utils, "get_parameter")
    def test_rejects_day_change_if_no_repayment_loan(
        self,
        mock_get_parameter: MagicMock,
    ):
        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"amortisation_method": "no_repayment"}
        )

        # run function
        hook_args = PreParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            updated_parameter_values={
                loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: sentinel.param
            },
        )
        result = loan.pre_parameter_change_hook(vault=sentinel.vault, hook_arguments=hook_args)

        expected_result = PreParameterChangeHookResult(
            rejection=Rejection(
                message=(
                    "It is not possible to change the due amount calculation day for a "
                    "No Repayment (Balloon Payment) loan."
                ),
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )
        self.assertEqual(result, expected_result)
