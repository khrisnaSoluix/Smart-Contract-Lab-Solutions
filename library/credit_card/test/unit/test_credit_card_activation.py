# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

# library
from library.credit_card.contracts.template import credit_card
from library.credit_card.test.unit.test_credit_card_common import CreditCardTestBase

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import ActivationHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    ActivationHookResult,
    PostingInstructionsDirective,
    ScheduledEvent,
    ScheduleFailover,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelCustomInstruction,
    SentinelEndOfMonthSchedule,
    SentinelScheduleExpression,
)


@patch.object(credit_card.utils, "get_end_of_month_schedule_from_parameters")
@patch.object(credit_card.utils, "get_parameter")
@patch.object(credit_card, "_get_first_scod")
@patch.object(credit_card, "_get_first_pdd")
@patch.object(credit_card.utils, "get_schedule_expression_from_parameters")
@patch.object(credit_card, "_make_internal_address_transfer")
class CreditCardActivationTest(CreditCardTestBase):
    # define common return types to avoid duplicated definitions across tests
    common_get_param_return_values: dict = {
        "payment_due_period": int("21"),
        "denomination": "GBP",
        "pdd_schedule_hour": "0",
        "pdd_schedule_minute": "0",
        "pdd_schedule_second": "0",
    }

    # create objects we expect for directives and schedules
    available_balance_ci = [SentinelCustomInstruction("available_balance_ci")]

    check_accrue_expression = SentinelScheduleExpression("check_accrue_event")

    # scod_start, scod_end
    scod_start_datetime = DEFAULT_DATETIME + relativedelta(months=1) - relativedelta(days=1)
    scod_function_result = (scod_start_datetime, scod_start_datetime + relativedelta(days=1))
    check_scod_expression = SentinelScheduleExpression("check_scod_event")

    check_annual_fee_expression = SentinelScheduleExpression("check_annual_fee_event")

    # originally _, pdd_end = _get_first_pdd(payment_due_period, scod_start)
    pdd_datetime = scod_start_datetime + relativedelta(
        days=common_get_param_return_values["payment_due_period"]
    )
    pdd_function_result = (pdd_datetime, pdd_datetime + relativedelta(days=1))
    check_pdd_expression = SentinelScheduleExpression("check_pdd_event")

    @patch.object(credit_card, "_create_custom_instructions")
    def test_available_balance_initialised_with_positive_credit_limit_on_account_activation(
        self,
        mock_create_custom_instructions: MagicMock,
        mock_make_internal_address_transfer: MagicMock,
        mock_get_schedule_expression_from_parameters: MagicMock,
        mock_get_first_pdd: MagicMock,
        mock_get_first_scod: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_end_of_month_schedule_from_parameters: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock()
        mock_create_custom_instructions.return_value = self.available_balance_ci
        mock_make_internal_address_transfer.return_value = self.available_balance_ci

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={**self.common_get_param_return_values, "credit_limit": Decimal("1000")},
        )
        mock_get_first_scod.return_value = self.scod_function_result
        mock_get_first_pdd.return_value = self.pdd_function_result

        mock_get_schedule_expression_from_parameters.side_effect = [
            self.check_accrue_expression,
            self.check_scod_expression,
            self.check_annual_fee_expression,
        ]

        mock_get_end_of_month_schedule_from_parameters.return_value = SentinelEndOfMonthSchedule(
            "pdd_schedule"
        )

        # construct expected result
        expected_custom_instructions = self.available_balance_ci

        expected_result = ActivationHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_custom_instructions,  # type: ignore
                    value_datetime=DEFAULT_DATETIME,
                )  # type: ignore
            ],
            scheduled_events_return_value={
                "ACCRUE_INTEREST": ScheduledEvent(
                    start_datetime=DEFAULT_DATETIME,
                    expression=self.check_accrue_expression,
                    skip=False,
                ),
                "STATEMENT_CUT_OFF": ScheduledEvent(
                    start_datetime=DEFAULT_DATETIME,
                    expression=self.check_scod_expression,
                    skip=False,
                ),
                "ANNUAL_FEE": ScheduledEvent(
                    start_datetime=DEFAULT_DATETIME,
                    expression=self.check_annual_fee_expression,
                    skip=False,
                ),
                "PAYMENT_DUE": ScheduledEvent(
                    start_datetime=self.pdd_function_result[1],
                    schedule_method=mock_get_end_of_month_schedule_from_parameters(
                        mock_vault,
                        credit_card.PDD_SCHEDULE_PREFIX,
                        ScheduleFailover.FIRST_VALID_DAY_BEFORE,
                        day=self.pdd_function_result[1].day,
                    ),
                ),
            },
        )

        # run hook
        hook_args = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = credit_card.activation_hook(vault=mock_vault, hook_arguments=hook_args)

        # validate result
        self.assertEqual(result, expected_result)

        mock_make_internal_address_transfer.assert_called_once_with(
            mock_vault,
            Decimal("1000"),
            "GBP",
            credit_internal=True,
            custom_address="AVAILABLE_BALANCE",
        )

        mock_get_first_scod.assert_called_with(DEFAULT_DATETIME)

        mock_get_first_pdd.assert_called_with(
            self.common_get_param_return_values["payment_due_period"],
            DEFAULT_DATETIME + relativedelta(months=1) - relativedelta(days=1),
        )

    def test_available_balance_initialised_with_zero_credit_limit_on_account_activation(
        self,
        mock_make_internal_address_transfer: MagicMock,
        mock_get_schedule_expression_from_parameters: MagicMock,
        mock_get_first_pdd: MagicMock,
        mock_get_first_scod: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_end_of_month_schedule_from_parameters: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock()
        mock_make_internal_address_transfer.return_value = self.available_balance_ci

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={**self.common_get_param_return_values, "credit_limit": Decimal("0")},
        )
        mock_get_first_scod.return_value = self.scod_function_result
        mock_get_first_pdd.return_value = self.pdd_function_result

        mock_get_schedule_expression_from_parameters.side_effect = [
            self.check_accrue_expression,
            self.check_scod_expression,
            self.check_annual_fee_expression,
        ]

        mock_get_end_of_month_schedule_from_parameters.return_value = SentinelEndOfMonthSchedule(
            "pdd_schedule"
        )

        # construct expected result
        expected_result = ActivationHookResult(
            posting_instructions_directives=[],
            scheduled_events_return_value={
                "ACCRUE_INTEREST": ScheduledEvent(
                    start_datetime=DEFAULT_DATETIME,
                    expression=self.check_accrue_expression,
                    skip=False,
                ),
                "STATEMENT_CUT_OFF": ScheduledEvent(
                    start_datetime=DEFAULT_DATETIME,
                    expression=self.check_scod_expression,
                    skip=False,
                ),
                "ANNUAL_FEE": ScheduledEvent(
                    start_datetime=DEFAULT_DATETIME,
                    expression=self.check_annual_fee_expression,
                    skip=False,
                ),
                "PAYMENT_DUE": ScheduledEvent(
                    start_datetime=self.pdd_function_result[1],
                    schedule_method=mock_get_end_of_month_schedule_from_parameters(
                        mock_vault,
                        credit_card.PDD_SCHEDULE_PREFIX,
                        ScheduleFailover.FIRST_VALID_DAY_BEFORE,
                        day=self.pdd_function_result[1].day,
                    ),
                ),
            },
        )

        # run hook
        hook_args = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = credit_card.activation_hook(vault=mock_vault, hook_arguments=hook_args)

        # validate result
        self.assertEqual(result, expected_result)

        mock_get_first_scod.assert_called_with(DEFAULT_DATETIME)

        mock_get_first_pdd.assert_called_with(
            self.common_get_param_return_values["payment_due_period"],
            DEFAULT_DATETIME + relativedelta(months=1) - relativedelta(days=1),
        )

    def test_available_balance_initialised_with_negative_credit_limit_on_account_activation(
        self,
        mock_make_internal_address_transfer: MagicMock,
        mock_get_schedule_expression_from_parameters: MagicMock,
        mock_get_first_pdd: MagicMock,
        mock_get_first_scod: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_end_of_month_schedule_from_parameters: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock()
        mock_make_internal_address_transfer.return_value = self.available_balance_ci

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={**self.common_get_param_return_values, "credit_limit": Decimal("-1000")},
        )
        mock_get_first_scod.return_value = self.scod_function_result
        mock_get_first_pdd.return_value = self.pdd_function_result

        mock_get_schedule_expression_from_parameters.side_effect = [
            self.check_accrue_expression,
            self.check_scod_expression,
            self.check_annual_fee_expression,
        ]

        mock_get_end_of_month_schedule_from_parameters.return_value = SentinelEndOfMonthSchedule(
            "pdd_schedule"
        )

        # construct expected result
        expected_result = ActivationHookResult(
            posting_instructions_directives=[],
            scheduled_events_return_value={
                "ACCRUE_INTEREST": ScheduledEvent(
                    start_datetime=DEFAULT_DATETIME,
                    expression=self.check_accrue_expression,
                    skip=False,
                ),
                "STATEMENT_CUT_OFF": ScheduledEvent(
                    start_datetime=DEFAULT_DATETIME,
                    expression=self.check_scod_expression,
                    skip=False,
                ),
                "ANNUAL_FEE": ScheduledEvent(
                    start_datetime=DEFAULT_DATETIME,
                    expression=self.check_annual_fee_expression,
                    skip=False,
                ),
                "PAYMENT_DUE": ScheduledEvent(
                    start_datetime=self.pdd_function_result[1],
                    schedule_method=mock_get_end_of_month_schedule_from_parameters(
                        mock_vault,
                        credit_card.PDD_SCHEDULE_PREFIX,
                        ScheduleFailover.FIRST_VALID_DAY_BEFORE,
                        day=self.pdd_function_result[1].day,
                    ),
                ),
            },
        )

        # run hook
        hook_args = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = credit_card.activation_hook(vault=mock_vault, hook_arguments=hook_args)

        # validate result
        self.assertEqual(result, expected_result)

        mock_get_first_scod.assert_called_with(DEFAULT_DATETIME)

        mock_get_first_pdd.assert_called_with(
            self.common_get_param_return_values["payment_due_period"],
            DEFAULT_DATETIME + relativedelta(months=1) - relativedelta(days=1),
        )


## TODO: ParameterMismatchTests once ActivationHook supports rejections

"""
Below is original list of unit tests that were directly translated over from CLV3.
TODO: the 3 CLV4 tests are only different in the credit_limit value passed in. We can simplify this.
The new CLV4 unit tests cover these scenarios:
    test_schedules_for_standard_parameters
    test_available_balance_initialised_with_credit_limit_on_account_activation
    test_available_balance_initialised_with_invalid_credit_limit_on_account_activation
    test_single_posting_batch_instructed_for_account_activation

TODO: These should be rewritten as simulation tests:
    test_schedules_for_account_created_mid_month - not covered, all sim tests start on 1/1

    test_schedule_day_set_to_last_when_landing_on_month_end - not clear what this does

    test_schedule_repayment_day_unchanged_when_pdd_falls_on_sunday - theres no contract logic that
    takes into account day of week, does this test even make sense?
"""
