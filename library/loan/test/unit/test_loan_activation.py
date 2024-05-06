# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# library
from library.loan.contracts.template import loan
from library.loan.test.unit.test_loan_common import DEFAULT_DATETIME, LoanTestBase

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import ActivationHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    ACCOUNT_ID,
    DEFAULT_HOOK_EXECUTION_ID,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    ActivationHookResult,
    CustomInstruction,
    PostingInstructionsDirective,
    ScheduledEvent,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    DEFAULT_POSTINGS,
    SentinelAccountNotificationDirective,
    SentinelCustomInstruction,
    SentinelScheduledEvent,
    SentinelScheduleExpression,
)


@patch.object(loan.balloon_payments, "is_balloon_loan")
@patch.object(loan.no_repayment, "is_no_repayment_loan")
@patch.object(loan, "_is_monthly_rest_loan")
@patch.object(loan, "_get_interest_rate_feature")
@patch.object(loan, "_get_activation_fee_custom_instruction")
@patch.object(loan, "_get_repayment_schedule_notification")
@patch.object(loan, "_get_amortisation_feature")
@patch.object(loan.emi, "amortise")
@patch.object(loan.disbursement, "get_disbursement_custom_instruction")
@patch.object(loan.due_amount_calculation, "scheduled_events")
@patch.object(loan.flat_interest, "is_flat_interest_loan")
@patch.object(loan.rule_of_78, "is_rule_of_78_loan")
@patch.object(loan.interest_accrual, "scheduled_events")
@patch.object(loan.overdue, "scheduled_events")
@patch.object(loan.utils, "get_parameter")
@patch.object(loan.utils, "get_schedule_expression_from_parameters")
class LoanActivationTest(LoanTestBase):
    # define common return types to avoid duplicated definitions across tests
    common_get_param_return_values = {
        "deposit_account": sentinel.deposit_account,
        "denomination": sentinel.denomination,
        "upfront_fee_income_account": sentinel.upfront_fee_account,
        "fixed_interest_loan": "False",
        "due_amount_calculation_day": "20",
    }

    disbursement_custom_instruction = [SentinelCustomInstruction("disbursement_ci")]
    emi_custom_instruction = [SentinelCustomInstruction("emi_ci")]
    fee_custom_instruction = [SentinelCustomInstruction("fee_ci")]

    check_delinquency_expression = SentinelScheduleExpression("check_delinquency_event")
    balloon_payment_expression = SentinelScheduleExpression("balloon_payment_event")
    check_overdue_expression = SentinelScheduleExpression("check_overdue_event")
    accrual_scheduled_event = {sentinel.accrual_event: SentinelScheduledEvent("accrual_event")}

    due_amount_calculation_scheduled_event = {
        sentinel.due_amount: SentinelScheduledEvent("due_amount_event")
    }
    overdue_scheduled_event = {sentinel.overdue: SentinelScheduledEvent("overdue_event")}
    repayment_schedule_notification = SentinelAccountNotificationDirective("repayment_schedule")

    disabled_balloon_schedule = {
        loan.balloon_payments.BALLOON_PAYMENT_EVENT: SentinelScheduledEvent("balloon_schedule")
    }

    @patch.object(loan.balloon_payments, "disabled_balloon_schedule")
    @patch.object(loan.utils, "create_postings")
    def test_activation_hook_no_fee_monthly_rest(
        self,
        mock_create_postings: MagicMock,
        mock_disabled_balloon_schedule: MagicMock,
        mock_get_schedule_expression_from_parameters: MagicMock,
        mock_get_parameter: MagicMock,
        mock_overdue_scheduled_events: MagicMock,
        mock_accrual_scheduled_events: MagicMock,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_due_amount_scheduled_events: MagicMock,
        mock_disbursement_custom_instruction: MagicMock,
        mock_amortise: MagicMock,
        mock_get_amortisation_feature: MagicMock,
        mock_get_repayment_schedule_notification: MagicMock,
        mock_get_activation_fee_custom_instruction: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_is_monthly_rest_loan: MagicMock,
        mock_is_no_repayment_loan: MagicMock,
        mock_is_balloon_loan: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock()
        mock_disbursement_custom_instruction.return_value = self.disbursement_custom_instruction
        mock_get_amortisation_feature.return_value = MagicMock(
            calculate_emi=MagicMock(return_value=Decimal("1"))
        )
        mock_amortise.return_value = self.emi_custom_instruction
        mock_get_activation_fee_custom_instruction.return_value = []
        sentinel.amortisation_method = MagicMock(upper=lambda: sentinel.amortisation_method)
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                **self.common_get_param_return_values,
                "upfront_fee": Decimal("0"),
                "amortise_upfront_fee": sentinel.false,
                "principal": sentinel.principal,
                "amortisation_method": sentinel.amortisation_method,
            }
        )
        mock_is_monthly_rest_loan.return_value = True
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = False
        mock_get_repayment_schedule_notification.return_value = self.repayment_schedule_notification
        mock_is_no_repayment_loan.return_value = False
        mock_is_balloon_loan.return_value = False
        mock_disabled_balloon_schedule.return_value = self.disabled_balloon_schedule

        tracker_postings = DEFAULT_POSTINGS
        mock_create_postings.return_value = tracker_postings
        tracker_ci = [
            CustomInstruction(
                postings=tracker_postings,
                override_all_restrictions=True,
                instruction_details={
                    "description": "Set principal at cycle start on activation",
                    "event": "LOAN_SET_PRINCIPAL_AT_CYCLE_START_ON_ACTIVATION",
                },
            )
        ]

        mock_accrual_scheduled_events.return_value = self.accrual_scheduled_event
        mock_due_amount_scheduled_events.return_value = self.due_amount_calculation_scheduled_event
        mock_overdue_scheduled_events.return_value = self.overdue_scheduled_event
        mock_get_schedule_expression_from_parameters.return_value = (
            self.check_delinquency_expression
        )
        mock_get_interest_rate_feature.return_value = sentinel.interest_rate_feature

        # construct expected result
        expected_custom_instructions = (
            self.disbursement_custom_instruction + tracker_ci + self.emi_custom_instruction
        )
        expected_schedule_start_datetime = DEFAULT_DATETIME + relativedelta(days=1)
        expected_result = ActivationHookResult(
            account_notification_directives=[self.repayment_schedule_notification],
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_custom_instructions,  # type: ignore
                    client_batch_id=f"LOAN_ACCOUNT_ACTIVATION_{DEFAULT_HOOK_EXECUTION_ID}",
                    value_datetime=DEFAULT_DATETIME,
                )  # type: ignore
            ],
            scheduled_events_return_value={
                **self.accrual_scheduled_event,
                **self.due_amount_calculation_scheduled_event,
                **self.disabled_balloon_schedule,
                loan.CHECK_DELINQUENCY: ScheduledEvent(
                    start_datetime=expected_schedule_start_datetime,
                    expression=self.check_delinquency_expression,
                    skip=True,
                ),
                **self.overdue_scheduled_event,
            },
        )

        # run hook
        hook_args = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = loan.activation_hook(vault=mock_vault, hook_arguments=hook_args)

        # validate result
        self.assertEqual(result, expected_result)
        mock_accrual_scheduled_events.assert_called_once_with(
            vault=mock_vault, start_datetime=expected_schedule_start_datetime, skip=False
        )
        mock_due_amount_scheduled_events.assert_called_once_with(
            vault=mock_vault, account_opening_datetime=DEFAULT_DATETIME
        )
        mock_overdue_scheduled_events.assert_called_once_with(
            vault=mock_vault,
            first_due_amount_calculation_datetime=DEFAULT_DATETIME
            + relativedelta(months=1, day=20),
            skip=True,
        )
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=mock_vault, parameter_prefix=loan.CHECK_DELINQUENCY_PREFIX
        )

        mock_disbursement_custom_instruction.assert_called_once_with(
            account_id=ACCOUNT_ID,
            deposit_account_id=sentinel.deposit_account,
            principal=sentinel.principal,
            denomination=sentinel.denomination,
        )
        mock_amortise.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=mock_get_amortisation_feature.return_value,
            interest_calculation_feature=sentinel.interest_rate_feature,
            principal_adjustments=[],
        )

        mock_get_activation_fee_custom_instruction.assert_called_once_with(
            account_id=ACCOUNT_ID,
            amount=Decimal("0"),
            denomination=sentinel.denomination,
            fee_income_account=sentinel.upfront_fee_account,
        )
        mock_get_repayment_schedule_notification.assert_called_once_with(vault=mock_vault)

    @patch.object(loan.balloon_payments, "disabled_balloon_schedule")
    def test_activation_hook_non_amortised_upfront_fee(
        self,
        mock_disabled_balloon_schedule: MagicMock,
        mock_get_schedule_expression_from_parameters: MagicMock,
        mock_get_parameter: MagicMock,
        mock_overdue_scheduled_events: MagicMock,
        mock_accrual_scheduled_events: MagicMock,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_due_amount_scheduled_events: MagicMock,
        mock_disbursement_custom_instruction: MagicMock,
        mock_amortise: MagicMock,
        mock_get_amortisation_feature: MagicMock,
        mock_get_repayment_schedule_notification: MagicMock,
        mock_get_activation_fee_custom_instruction: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_is_monthly_rest_loan: MagicMock,
        mock_is_no_repayment_loan: MagicMock,
        mock_is_balloon_loan: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock()
        mock_disbursement_custom_instruction.return_value = self.disbursement_custom_instruction
        mock_get_amortisation_feature.return_value = MagicMock(
            calculate_emi=MagicMock(return_value=Decimal("1"))
        )
        mock_amortise.return_value = self.emi_custom_instruction
        mock_get_activation_fee_custom_instruction.return_value = self.fee_custom_instruction
        sentinel.amortisation_method = MagicMock(upper=lambda: sentinel.amortisation_method)
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                **self.common_get_param_return_values,
                "upfront_fee": Decimal("10"),
                "amortise_upfront_fee": False,
                "principal": Decimal("100"),
                "amortisation_method": sentinel.amortisation_method,
            }
        )
        mock_is_monthly_rest_loan.return_value = False
        mock_get_repayment_schedule_notification.return_value = self.repayment_schedule_notification

        mock_accrual_scheduled_events.return_value = self.accrual_scheduled_event
        mock_due_amount_scheduled_events.return_value = self.due_amount_calculation_scheduled_event
        mock_overdue_scheduled_events.return_value = self.overdue_scheduled_event
        mock_get_schedule_expression_from_parameters.return_value = (
            self.check_delinquency_expression
        )
        mock_get_interest_rate_feature.return_value = sentinel.interest_rate_feature
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = False
        mock_is_no_repayment_loan.return_value = False
        mock_is_balloon_loan.return_value = False
        mock_disabled_balloon_schedule.return_value = self.disabled_balloon_schedule

        # construct expected result
        expected_custom_instructions = (
            self.disbursement_custom_instruction
            + self.emi_custom_instruction
            + self.fee_custom_instruction
        )
        expected_schedule_start_datetime = DEFAULT_DATETIME + relativedelta(days=1)
        expected_result = ActivationHookResult(
            account_notification_directives=[self.repayment_schedule_notification],
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_custom_instructions,  # type: ignore
                    client_batch_id=f"LOAN_ACCOUNT_ACTIVATION_{DEFAULT_HOOK_EXECUTION_ID}",
                    value_datetime=DEFAULT_DATETIME,
                )  # type: ignore
            ],
            scheduled_events_return_value={
                **self.accrual_scheduled_event,
                **self.due_amount_calculation_scheduled_event,
                **self.disabled_balloon_schedule,
                loan.CHECK_DELINQUENCY: ScheduledEvent(
                    start_datetime=expected_schedule_start_datetime,
                    expression=self.check_delinquency_expression,
                    skip=True,
                ),
                **self.overdue_scheduled_event,
            },
        )

        # run hook
        hook_args = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = loan.activation_hook(vault=mock_vault, hook_arguments=hook_args)

        # validate result
        self.assertEqual(result, expected_result)
        mock_accrual_scheduled_events.assert_called_once_with(
            vault=mock_vault, start_datetime=expected_schedule_start_datetime, skip=False
        )
        mock_due_amount_scheduled_events.assert_called_once_with(
            vault=mock_vault, account_opening_datetime=DEFAULT_DATETIME
        )
        mock_overdue_scheduled_events.assert_called_once_with(
            vault=mock_vault,
            first_due_amount_calculation_datetime=DEFAULT_DATETIME
            + relativedelta(months=1, day=20),
            skip=True,
        )
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=mock_vault, parameter_prefix=loan.CHECK_DELINQUENCY_PREFIX
        )

        mock_disbursement_custom_instruction.assert_called_once_with(
            account_id=ACCOUNT_ID,
            deposit_account_id=sentinel.deposit_account,
            principal=Decimal("90"),
            denomination=sentinel.denomination,
        )
        mock_amortise.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=mock_get_amortisation_feature.return_value,
            interest_calculation_feature=sentinel.interest_rate_feature,
            principal_adjustments=[],
        )

        mock_get_activation_fee_custom_instruction.assert_called_once_with(
            account_id=ACCOUNT_ID,
            amount=Decimal("10"),
            denomination=sentinel.denomination,
            fee_income_account=sentinel.upfront_fee_account,
        )
        mock_get_repayment_schedule_notification.assert_called_once_with(vault=mock_vault)

    @patch.object(loan.balloon_payments, "disabled_balloon_schedule")
    @patch.object(loan.lending_interfaces, "PrincipalAdjustment")
    def test_activation_hook_amortised_upfront_fee(
        self,
        mock_PrincipalAdjustment: MagicMock,
        mock_disabled_balloon_schedule: MagicMock,
        mock_get_schedule_expression_from_parameters: MagicMock,
        mock_get_parameter: MagicMock,
        mock_overdue_scheduled_events: MagicMock,
        mock_accrual_scheduled_events: MagicMock,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_due_amount_scheduled_events: MagicMock,
        mock_disbursement_custom_instruction: MagicMock,
        mock_amortise: MagicMock,
        mock_get_amortisation_feature: MagicMock,
        mock_get_repayment_schedule_notification: MagicMock,
        mock_get_activation_fee_custom_instruction: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_is_monthly_rest_loan: MagicMock,
        mock_is_no_repayment_loan: MagicMock,
        mock_is_balloon_loan: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock()

        mock_disbursement_custom_instruction.return_value = self.disbursement_custom_instruction
        mock_get_amortisation_feature.return_value = MagicMock(
            calculate_emi=MagicMock(return_value=Decimal("1"))
        )
        mock_amortise.return_value = self.emi_custom_instruction
        mock_get_activation_fee_custom_instruction.return_value = self.fee_custom_instruction
        mock_PrincipalAdjustment.return_value = sentinel.PrincipalAdjustment
        sentinel.amortisation_method = MagicMock(upper=lambda: sentinel.amortisation_method)
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                **self.common_get_param_return_values,
                "upfront_fee": Decimal("10"),
                "amortise_upfront_fee": True,
                "principal": Decimal("100"),
                "amortisation_method": sentinel.amortisation_method,
            }
        )
        mock_is_monthly_rest_loan.return_value = False

        mock_accrual_scheduled_events.return_value = self.accrual_scheduled_event
        mock_due_amount_scheduled_events.return_value = self.due_amount_calculation_scheduled_event
        mock_overdue_scheduled_events.return_value = self.overdue_scheduled_event
        mock_get_schedule_expression_from_parameters.return_value = (
            self.check_delinquency_expression
        )
        mock_get_interest_rate_feature.return_value = sentinel.interest_rate_feature
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = False
        mock_get_repayment_schedule_notification.return_value = self.repayment_schedule_notification
        mock_is_no_repayment_loan.return_value = False
        mock_is_balloon_loan.return_value = False
        mock_disabled_balloon_schedule.return_value = self.disabled_balloon_schedule

        # construct expected result
        expected_custom_instructions = (
            self.disbursement_custom_instruction
            + self.emi_custom_instruction
            + self.fee_custom_instruction
        )
        expected_schedule_start_datetime = DEFAULT_DATETIME + relativedelta(days=1)
        expected_result = ActivationHookResult(
            account_notification_directives=[self.repayment_schedule_notification],
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_custom_instructions,  # type: ignore
                    client_batch_id=f"LOAN_ACCOUNT_ACTIVATION_{DEFAULT_HOOK_EXECUTION_ID}",
                    value_datetime=DEFAULT_DATETIME,
                )  # type: ignore
            ],
            scheduled_events_return_value={
                **self.accrual_scheduled_event,
                **self.due_amount_calculation_scheduled_event,
                **self.disabled_balloon_schedule,
                loan.CHECK_DELINQUENCY: ScheduledEvent(
                    start_datetime=expected_schedule_start_datetime,
                    expression=self.check_delinquency_expression,
                    skip=True,
                ),
                **self.overdue_scheduled_event,
            },
        )

        # run hook
        hook_args = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = loan.activation_hook(vault=mock_vault, hook_arguments=hook_args)

        # validate result
        self.assertEqual(result, expected_result)
        mock_accrual_scheduled_events.assert_called_once_with(
            vault=mock_vault, start_datetime=expected_schedule_start_datetime, skip=False
        )
        mock_due_amount_scheduled_events.assert_called_once_with(
            vault=mock_vault, account_opening_datetime=DEFAULT_DATETIME
        )
        mock_overdue_scheduled_events.assert_called_once_with(
            vault=mock_vault,
            first_due_amount_calculation_datetime=DEFAULT_DATETIME
            + relativedelta(months=1, day=20),
            skip=True,
        )
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=mock_vault, parameter_prefix=loan.CHECK_DELINQUENCY_PREFIX
        )

        mock_disbursement_custom_instruction.assert_called_once_with(
            account_id=ACCOUNT_ID,
            deposit_account_id=sentinel.deposit_account,
            principal=Decimal("100"),
            denomination=sentinel.denomination,
        )
        mock_amortise.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=mock_get_amortisation_feature.return_value,
            interest_calculation_feature=sentinel.interest_rate_feature,
            principal_adjustments=[sentinel.PrincipalAdjustment],
        )

        mock_get_activation_fee_custom_instruction.assert_called_once_with(
            account_id=ACCOUNT_ID,
            amount=Decimal("10"),
            denomination=sentinel.denomination,
            fee_income_account=sentinel.upfront_fee_account,
        )
        mock_get_repayment_schedule_notification.assert_called_once_with(vault=mock_vault)

    @patch.object(loan.balloon_payments, "disabled_balloon_schedule")
    @patch.object(loan.utils, "create_postings")
    def test_activation_hook_flat_interest_accrual_skipped(
        self,
        mock_create_postings: MagicMock,
        mock_disabled_balloon_schedule: MagicMock,
        mock_get_schedule_expression_from_parameters: MagicMock,
        mock_get_parameter: MagicMock,
        mock_overdue_scheduled_events: MagicMock,
        mock_accrual_scheduled_events: MagicMock,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_due_amount_scheduled_events: MagicMock,
        mock_disbursement_custom_instruction: MagicMock,
        mock_get_emi_instructions: MagicMock,
        mock_get_amortisation_feature: MagicMock,
        mock_get_repayment_schedule_notification: MagicMock,
        mock_get_activation_fee_custom_instruction: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_is_monthly_rest_loan: MagicMock,
        mock_is_no_repayment_loan: MagicMock,
        mock_is_balloon_loan: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock()
        mock_disbursement_custom_instruction.return_value = self.disbursement_custom_instruction
        mock_get_emi_instructions.return_value = self.emi_custom_instruction
        mock_get_activation_fee_custom_instruction.return_value = []
        mock_get_amortisation_feature.return_value = MagicMock(
            calculate_emi=MagicMock(return_value=Decimal("1"))
        )
        sentinel.amortisation_method = MagicMock(upper=lambda: sentinel.amortisation_method)
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                **self.common_get_param_return_values,
                "upfront_fee": Decimal("0"),
                "amortise_upfront_fee": sentinel.false,
                "principal": sentinel.principal,
                "amortisation_method": sentinel.amortisation_method,
            }
        )
        mock_is_monthly_rest_loan.return_value = False
        mock_is_flat_interest_loan.return_value = True
        mock_is_rule_of_78_loan.return_value = False
        mock_get_repayment_schedule_notification.return_value = self.repayment_schedule_notification

        tracker_postings = DEFAULT_POSTINGS
        mock_create_postings.return_value = tracker_postings

        mock_accrual_scheduled_events.return_value = self.accrual_scheduled_event
        mock_due_amount_scheduled_events.return_value = self.due_amount_calculation_scheduled_event
        mock_overdue_scheduled_events.return_value = self.overdue_scheduled_event
        mock_get_schedule_expression_from_parameters.return_value = (
            self.check_delinquency_expression
        )
        mock_get_interest_rate_feature.return_value = sentinel.interest_rate_feature
        mock_is_no_repayment_loan.return_value = False
        mock_is_balloon_loan.return_value = False
        mock_disabled_balloon_schedule.return_value = self.disabled_balloon_schedule

        # construct expected result
        expected_custom_instructions = (
            self.disbursement_custom_instruction + self.emi_custom_instruction
        )
        expected_schedule_start_datetime = DEFAULT_DATETIME + relativedelta(days=1)
        expected_result = ActivationHookResult(
            account_notification_directives=[self.repayment_schedule_notification],
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_custom_instructions,  # type: ignore
                    client_batch_id=f"LOAN_ACCOUNT_ACTIVATION_{DEFAULT_HOOK_EXECUTION_ID}",
                    value_datetime=DEFAULT_DATETIME,
                )  # type: ignore
            ],
            scheduled_events_return_value={
                **self.accrual_scheduled_event,
                **self.due_amount_calculation_scheduled_event,
                **self.disabled_balloon_schedule,
                loan.CHECK_DELINQUENCY: ScheduledEvent(
                    start_datetime=expected_schedule_start_datetime,
                    expression=self.check_delinquency_expression,
                    skip=True,
                ),
                **self.overdue_scheduled_event,
            },
        )

        # run hook
        hook_args = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = loan.activation_hook(vault=mock_vault, hook_arguments=hook_args)

        # validate result
        self.assertEqual(result, expected_result)

        mock_accrual_scheduled_events.assert_called_once_with(
            vault=mock_vault, start_datetime=expected_schedule_start_datetime, skip=True
        )
        mock_due_amount_scheduled_events.assert_called_once_with(
            vault=mock_vault, account_opening_datetime=DEFAULT_DATETIME
        )
        mock_overdue_scheduled_events.assert_called_once_with(
            vault=mock_vault,
            first_due_amount_calculation_datetime=DEFAULT_DATETIME
            + relativedelta(months=1, day=20),
            skip=True,
        )
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=mock_vault, parameter_prefix=loan.CHECK_DELINQUENCY_PREFIX
        )

        mock_disbursement_custom_instruction.assert_called_once_with(
            account_id=ACCOUNT_ID,
            deposit_account_id=sentinel.deposit_account,
            principal=sentinel.principal,
            denomination=sentinel.denomination,
        )
        mock_get_emi_instructions.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=mock_get_amortisation_feature.return_value,
            interest_calculation_feature=sentinel.interest_rate_feature,
            principal_adjustments=[],
        )

        mock_get_activation_fee_custom_instruction.assert_called_once_with(
            account_id=ACCOUNT_ID,
            amount=Decimal("0"),
            denomination=sentinel.denomination,
            fee_income_account=sentinel.upfront_fee_account,
        )
        mock_get_repayment_schedule_notification.assert_called_once_with(vault=mock_vault)

    @patch.object(loan.balloon_payments, "disabled_balloon_schedule")
    @patch.object(loan.utils, "create_postings")
    def test_activation_hook_rule_of_78_accrual_skipped(
        self,
        mock_create_postings: MagicMock,
        mock_disabled_balloon_schedule: MagicMock,
        mock_get_schedule_expression_from_parameters: MagicMock,
        mock_get_parameter: MagicMock,
        mock_overdue_scheduled_events: MagicMock,
        mock_accrual_scheduled_events: MagicMock,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_due_amount_scheduled_events: MagicMock,
        mock_disbursement_custom_instruction: MagicMock,
        mock_get_emi_instructions: MagicMock,
        mock_get_amortisation_feature: MagicMock,
        mock_get_repayment_schedule_notification: MagicMock,
        mock_get_activation_fee_custom_instruction: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_is_monthly_rest_loan: MagicMock,
        mock_is_no_repayment_loan: MagicMock,
        mock_is_balloon_loan: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock()
        mock_disbursement_custom_instruction.return_value = self.disbursement_custom_instruction
        mock_get_emi_instructions.return_value = self.emi_custom_instruction
        mock_get_activation_fee_custom_instruction.return_value = []
        mock_get_amortisation_feature.return_value = MagicMock(
            calculate_emi=MagicMock(return_value=Decimal("1"))
        )
        sentinel.amortisation_method = MagicMock(upper=lambda: sentinel.amortisation_method)
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                **self.common_get_param_return_values,
                "upfront_fee": Decimal("0"),
                "amortise_upfront_fee": sentinel.false,
                "principal": sentinel.principal,
                "amortisation_method": sentinel.amortisation_method,
            }
        )
        mock_is_monthly_rest_loan.return_value = False
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = True
        mock_get_repayment_schedule_notification.return_value = self.repayment_schedule_notification

        tracker_postings = DEFAULT_POSTINGS
        mock_create_postings.return_value = tracker_postings

        mock_accrual_scheduled_events.return_value = self.accrual_scheduled_event
        mock_due_amount_scheduled_events.return_value = self.due_amount_calculation_scheduled_event
        mock_overdue_scheduled_events.return_value = self.overdue_scheduled_event
        mock_get_schedule_expression_from_parameters.return_value = (
            self.check_delinquency_expression
        )
        mock_get_interest_rate_feature.return_value = sentinel.interest_rate_feature
        mock_is_no_repayment_loan.return_value = False
        mock_is_balloon_loan.return_value = False
        mock_disabled_balloon_schedule.return_value = self.disabled_balloon_schedule

        # construct expected result
        expected_custom_instructions = (
            self.disbursement_custom_instruction + self.emi_custom_instruction
        )
        expected_schedule_start_datetime = DEFAULT_DATETIME + relativedelta(days=1)
        expected_result = ActivationHookResult(
            account_notification_directives=[self.repayment_schedule_notification],
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_custom_instructions,  # type: ignore
                    client_batch_id=f"LOAN_ACCOUNT_ACTIVATION_{DEFAULT_HOOK_EXECUTION_ID}",
                    value_datetime=DEFAULT_DATETIME,
                )  # type: ignore
            ],
            scheduled_events_return_value={
                **self.accrual_scheduled_event,
                **self.due_amount_calculation_scheduled_event,
                **self.disabled_balloon_schedule,
                loan.CHECK_DELINQUENCY: ScheduledEvent(
                    start_datetime=expected_schedule_start_datetime,
                    expression=self.check_delinquency_expression,
                    skip=True,
                ),
                **self.overdue_scheduled_event,
            },
        )

        # run hook
        hook_args = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = loan.activation_hook(vault=mock_vault, hook_arguments=hook_args)

        # validate result
        self.assertEqual(result, expected_result)

        mock_accrual_scheduled_events.assert_called_once_with(
            vault=mock_vault, start_datetime=expected_schedule_start_datetime, skip=True
        )
        mock_due_amount_scheduled_events.assert_called_once_with(
            vault=mock_vault, account_opening_datetime=DEFAULT_DATETIME
        )
        mock_overdue_scheduled_events.assert_called_once_with(
            vault=mock_vault,
            first_due_amount_calculation_datetime=DEFAULT_DATETIME
            + relativedelta(months=1, day=20),
            skip=True,
        )
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=mock_vault, parameter_prefix=loan.CHECK_DELINQUENCY_PREFIX
        )

        mock_disbursement_custom_instruction.assert_called_once_with(
            account_id=ACCOUNT_ID,
            deposit_account_id=sentinel.deposit_account,
            principal=sentinel.principal,
            denomination=sentinel.denomination,
        )
        mock_get_emi_instructions.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=mock_get_amortisation_feature.return_value,
            interest_calculation_feature=sentinel.interest_rate_feature,
            principal_adjustments=[],
        )

        mock_get_activation_fee_custom_instruction.assert_called_once_with(
            account_id=ACCOUNT_ID,
            amount=Decimal("0"),
            denomination=sentinel.denomination,
            fee_income_account=sentinel.upfront_fee_account,
        )
        mock_get_repayment_schedule_notification.assert_called_once_with(vault=mock_vault)

    @patch.object(loan.balloon_payments, "scheduled_events")
    def test_activation_hook_balloon_payment(
        self,
        mock_balloon_scheduled_events: MagicMock,
        mock_get_schedule_expression_from_parameters: MagicMock,
        mock_get_parameter: MagicMock,
        mock_overdue_scheduled_events: MagicMock,
        mock_accrual_scheduled_events: MagicMock,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_due_amount_scheduled_events: MagicMock,
        mock_disbursement_custom_instruction: MagicMock,
        mock_amortise: MagicMock,
        mock_get_amortisation_feature: MagicMock,
        mock_get_repayment_schedule_notification: MagicMock,
        mock_get_activation_fee_custom_instruction: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_is_monthly_rest_loan: MagicMock,
        mock_is_no_repayment_loan: MagicMock,
        mock_is_balloon_loan: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock()
        mock_disbursement_custom_instruction.return_value = self.disbursement_custom_instruction
        mock_get_amortisation_feature.return_value = MagicMock(
            calculate_emi=MagicMock(return_value=Decimal("1"))
        )
        mock_amortise.return_value = self.emi_custom_instruction
        mock_get_activation_fee_custom_instruction.return_value = self.fee_custom_instruction
        sentinel.amortisation_method = MagicMock(upper=lambda: sentinel.amortisation_method)
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                **self.common_get_param_return_values,
                "upfront_fee": Decimal("10"),
                "amortise_upfront_fee": False,
                "principal": Decimal("100"),
                "amortisation_method": "MINIMUM_REPAYMENT_WITH_BALLOON_PAYMENT",
            }
        )
        mock_is_monthly_rest_loan.return_value = False
        mock_get_repayment_schedule_notification.return_value = self.repayment_schedule_notification

        mock_accrual_scheduled_events.return_value = self.accrual_scheduled_event
        mock_due_amount_scheduled_events.return_value = self.due_amount_calculation_scheduled_event
        mock_overdue_scheduled_events.return_value = self.overdue_scheduled_event
        mock_get_schedule_expression_from_parameters.return_value = (
            self.check_delinquency_expression
        )
        mock_get_interest_rate_feature.return_value = sentinel.interest_rate_feature
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = False
        mock_is_no_repayment_loan.return_value = False
        mock_is_balloon_loan.return_value = True
        balloon_schedules = {
            sentinel.balloon_event: SentinelScheduledEvent("balloon"),
            sentinel.due_calc_event: SentinelScheduledEvent("due_calc"),
        }
        mock_balloon_scheduled_events.return_value = balloon_schedules

        # construct expected result
        expected_custom_instructions = (
            self.disbursement_custom_instruction
            + self.emi_custom_instruction
            + self.fee_custom_instruction
        )
        expected_schedule_start_datetime = DEFAULT_DATETIME + relativedelta(days=1)
        expected_result = ActivationHookResult(
            account_notification_directives=[self.repayment_schedule_notification],
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_custom_instructions,  # type: ignore
                    client_batch_id=f"LOAN_ACCOUNT_ACTIVATION_{DEFAULT_HOOK_EXECUTION_ID}",
                    value_datetime=DEFAULT_DATETIME,
                )  # type: ignore
            ],
            scheduled_events_return_value={
                **self.accrual_scheduled_event,
                **balloon_schedules,
                loan.CHECK_DELINQUENCY: ScheduledEvent(
                    start_datetime=expected_schedule_start_datetime,
                    expression=self.check_delinquency_expression,
                    skip=True,
                ),
                **self.overdue_scheduled_event,
            },
        )

        # run hook
        hook_args = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = loan.activation_hook(vault=mock_vault, hook_arguments=hook_args)

        # validate result
        self.assertEqual(result, expected_result)
        mock_accrual_scheduled_events.assert_called_once_with(
            vault=mock_vault, start_datetime=expected_schedule_start_datetime, skip=False
        )

        mock_overdue_scheduled_events.assert_called_once_with(
            vault=mock_vault,
            first_due_amount_calculation_datetime=DEFAULT_DATETIME
            + relativedelta(months=1, day=20),
            skip=True,
        )
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=mock_vault, parameter_prefix=loan.CHECK_DELINQUENCY_PREFIX
        )

        mock_disbursement_custom_instruction.assert_called_once_with(
            account_id=ACCOUNT_ID,
            deposit_account_id=sentinel.deposit_account,
            principal=Decimal("90"),
            denomination=sentinel.denomination,
        )

        mock_get_activation_fee_custom_instruction.assert_called_once_with(
            account_id=ACCOUNT_ID,
            amount=Decimal("10"),
            denomination=sentinel.denomination,
            fee_income_account=sentinel.upfront_fee_account,
        )
        mock_get_repayment_schedule_notification.assert_called_once_with(vault=mock_vault)

    @patch.object(loan.balloon_payments, "scheduled_events")
    @patch.object(loan.utils, "create_end_of_time_schedule")
    def test_activation_hook_no_repayment_balloon_payment(
        self,
        mock_create_end_of_time_schedule: MagicMock,
        mock_balloon_scheduled_events: MagicMock,
        mock_get_schedule_expression_from_parameters: MagicMock,
        mock_get_parameter: MagicMock,
        mock_overdue_scheduled_events: MagicMock,
        mock_accrual_scheduled_events: MagicMock,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_due_amount_scheduled_events: MagicMock,
        mock_disbursement_custom_instruction: MagicMock,
        mock_amortise: MagicMock,
        mock_get_amortisation_feature: MagicMock,
        mock_get_repayment_schedule_notification: MagicMock,
        mock_get_activation_fee_custom_instruction: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_is_monthly_rest_loan: MagicMock,
        mock_is_no_repayment_loan: MagicMock,
        mock_is_balloon_loan: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock()
        mock_disbursement_custom_instruction.return_value = self.disbursement_custom_instruction
        mock_get_amortisation_feature.return_value = MagicMock(
            calculate_emi=MagicMock(return_value=Decimal("1"))
        )
        mock_amortise.return_value = self.emi_custom_instruction
        mock_get_activation_fee_custom_instruction.return_value = self.fee_custom_instruction
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                **self.common_get_param_return_values,
                "upfront_fee": Decimal("10"),
                "amortise_upfront_fee": False,
                "principal": Decimal("100"),
                "amortisation_method": "no_repayment",
            }
        )
        mock_is_monthly_rest_loan.return_value = False
        mock_get_repayment_schedule_notification.return_value = self.repayment_schedule_notification

        mock_accrual_scheduled_events.return_value = self.accrual_scheduled_event
        mock_get_interest_rate_feature.return_value = sentinel.interest_rate_feature
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = False
        overdue_scheduled_event = SentinelScheduledEvent("overdue")
        delinquency_scheduled_event = SentinelScheduledEvent("delinquency")
        mock_create_end_of_time_schedule.side_effect = [
            overdue_scheduled_event,
            delinquency_scheduled_event,
        ]
        mock_is_no_repayment_loan.return_value = True
        mock_is_balloon_loan.return_value = True
        balloon_schedules = {
            sentinel.balloon_event: SentinelScheduledEvent("balloon"),
            sentinel.due_calc_event: SentinelScheduledEvent("due_calc"),
        }
        mock_balloon_scheduled_events.return_value = balloon_schedules

        # construct expected result
        expected_custom_instructions = (
            self.disbursement_custom_instruction
            + self.emi_custom_instruction
            + self.fee_custom_instruction
        )
        expected_schedule_start_datetime = DEFAULT_DATETIME + relativedelta(days=1)
        expected_result = ActivationHookResult(
            account_notification_directives=[self.repayment_schedule_notification],
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_custom_instructions,  # type: ignore
                    client_batch_id=f"LOAN_ACCOUNT_ACTIVATION_{DEFAULT_HOOK_EXECUTION_ID}",
                    value_datetime=DEFAULT_DATETIME,
                )  # type: ignore
            ],
            scheduled_events_return_value={
                **self.accrual_scheduled_event,
                **balloon_schedules,
                loan.overdue.CHECK_OVERDUE_EVENT: overdue_scheduled_event,
                loan.CHECK_DELINQUENCY: delinquency_scheduled_event,
            },
        )

        # run hook
        hook_args = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = loan.activation_hook(vault=mock_vault, hook_arguments=hook_args)

        # validate result
        self.assertEqual(result, expected_result)
        mock_accrual_scheduled_events.assert_called_once_with(
            vault=mock_vault, start_datetime=expected_schedule_start_datetime, skip=False
        )

        mock_overdue_scheduled_events.assert_not_called()
        mock_due_amount_scheduled_events.assert_not_called()
        mock_get_schedule_expression_from_parameters.assert_not_called()
        mock_disbursement_custom_instruction.assert_called_once_with(
            account_id=ACCOUNT_ID,
            deposit_account_id=sentinel.deposit_account,
            principal=Decimal("90"),
            denomination=sentinel.denomination,
        )

        mock_get_activation_fee_custom_instruction.assert_called_once_with(
            account_id=ACCOUNT_ID,
            amount=Decimal("10"),
            denomination=sentinel.denomination,
            fee_income_account=sentinel.upfront_fee_account,
        )
        mock_get_repayment_schedule_notification.assert_called_once_with(vault=mock_vault)
