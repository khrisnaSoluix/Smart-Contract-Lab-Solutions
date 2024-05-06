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
from contracts_api import PreParameterChangeHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PreParameterChangeHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelRejection,
)

PARAM_CREDIT_LIMIT = line_of_credit.credit_limit.PARAM_CREDIT_LIMIT
PARAM_DUE_AMOUNT_CALCULATION_DAY = (
    line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
)


@patch.object(line_of_credit.due_amount_calculation, "validate_due_amount_calculation_day_change")
@patch.object(line_of_credit.credit_limit, "validate_credit_limit_parameter_change")
class LineOfCreditPreParameterChangeTest(LineOfCreditTestBase):
    def test_pre_parameter_change_hook_no_parameter_changes(
        self,
        mock_validate_credit_limit_parameter_change: MagicMock,
        mock_validate_due_amount_calculation_day_change: MagicMock,
    ):
        hook_arguments = PreParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            updated_parameter_values={},
        )
        result = line_of_credit.pre_parameter_change_hook(
            vault=sentinel.vault, hook_arguments=hook_arguments
        )

        self.assertIsNone(result)

        mock_validate_due_amount_calculation_day_change.assert_not_called()
        mock_validate_credit_limit_parameter_change.assert_not_called()

    def test_pre_parameter_change_hook_param_changed_that_has_no_validation(
        self,
        mock_validate_credit_limit_parameter_change: MagicMock,
        mock_validate_due_amount_calculation_day_change: MagicMock,
    ):
        hook_arguments = PreParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            updated_parameter_values={"dummy_parameter": "dummy value"},
        )
        result = line_of_credit.pre_parameter_change_hook(
            vault=sentinel.vault, hook_arguments=hook_arguments
        )

        self.assertIsNone(result)

        mock_validate_due_amount_calculation_day_change.assert_not_called()
        mock_validate_credit_limit_parameter_change.assert_not_called()

    def test_pre_parameter_change_hook_valid_change_to_due_amount_calc_day(
        self,
        mock_validate_credit_limit_parameter_change: MagicMock,
        mock_validate_due_amount_calculation_day_change: MagicMock,
    ):
        mock_validate_due_amount_calculation_day_change.return_value = None
        hook_arguments = PreParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            updated_parameter_values={PARAM_DUE_AMOUNT_CALCULATION_DAY: sentinel.due_calc_day},
        )
        result = line_of_credit.pre_parameter_change_hook(
            vault=sentinel.vault, hook_arguments=hook_arguments
        )

        self.assertIsNone(result)

        mock_validate_due_amount_calculation_day_change.assert_called_once_with(
            vault=sentinel.vault
        )
        mock_validate_credit_limit_parameter_change.assert_not_called()

    def test_pre_parameter_change_hook_rejects_invalid_change_to_due_amount_calc_day(
        self,
        mock_validate_credit_limit_parameter_change: MagicMock,
        mock_validate_due_amount_calculation_day_change: MagicMock,
    ):
        due_amount_day_rejection = SentinelRejection("rejection")
        mock_validate_due_amount_calculation_day_change.return_value = due_amount_day_rejection
        hook_arguments = PreParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            updated_parameter_values={PARAM_DUE_AMOUNT_CALCULATION_DAY: sentinel.due_calc_day},
        )
        expected_result = PreParameterChangeHookResult(rejection=due_amount_day_rejection)
        result = line_of_credit.pre_parameter_change_hook(
            vault=sentinel.vault, hook_arguments=hook_arguments
        )

        self.assertEqual(result, expected_result)

        mock_validate_due_amount_calculation_day_change.assert_called_once_with(
            vault=sentinel.vault
        )
        mock_validate_credit_limit_parameter_change.assert_not_called()

    def test_pre_parameter_change_hook_valid_change_to_credit_limit(
        self,
        mock_validate_credit_limit_parameter_change: MagicMock,
        mock_validate_due_amount_calculation_day_change: MagicMock,
    ):
        mock_validate_credit_limit_parameter_change.return_value = None
        hook_arguments = PreParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            updated_parameter_values={PARAM_CREDIT_LIMIT: sentinel.credit_limit},
        )
        result = line_of_credit.pre_parameter_change_hook(
            vault=sentinel.vault, hook_arguments=hook_arguments
        )

        self.assertIsNone(result)

        mock_validate_due_amount_calculation_day_change.assert_not_called()
        mock_validate_credit_limit_parameter_change.assert_called_once_with(
            vault=sentinel.vault,
            proposed_credit_limit=sentinel.credit_limit,
            principal_addresses=[
                "TOTAL_PRINCIPAL",
                "TOTAL_PRINCIPAL_DUE",
                "TOTAL_PRINCIPAL_OVERDUE",
            ],
        )

    def test_pre_parameter_change_hook_rejects_invalid_change_to_credit_limit(
        self,
        mock_validate_credit_limit_parameter_change: MagicMock,
        mock_validate_due_amount_calculation_day_change: MagicMock,
    ):
        credit_limit_rejection = SentinelRejection("rejection")
        mock_validate_credit_limit_parameter_change.return_value = credit_limit_rejection
        hook_arguments = PreParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            updated_parameter_values={PARAM_CREDIT_LIMIT: sentinel.credit_limit},
        )
        expected_result = PreParameterChangeHookResult(rejection=credit_limit_rejection)
        result = line_of_credit.pre_parameter_change_hook(
            vault=sentinel.vault, hook_arguments=hook_arguments
        )

        self.assertEqual(result, expected_result)

        mock_validate_due_amount_calculation_day_change.assert_not_called()
        mock_validate_credit_limit_parameter_change.assert_called_once_with(
            vault=sentinel.vault,
            proposed_credit_limit=sentinel.credit_limit,
            principal_addresses=[
                "TOTAL_PRINCIPAL",
                "TOTAL_PRINCIPAL_DUE",
                "TOTAL_PRINCIPAL_OVERDUE",
            ],
        )
