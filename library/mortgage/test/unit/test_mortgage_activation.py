# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from dateutil.relativedelta import relativedelta
from unittest.mock import MagicMock, patch, sentinel

# library
import library.mortgage.contracts.template.mortgage as mortgage
from library.mortgage.test.unit.test_mortgage_common import MortgageTestBase

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import ActivationHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    ScheduledEvent,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelCustomInstruction,
    SentinelScheduledEvent,
    SentinelScheduleExpression,
)


class ActivationTest(MortgageTestBase):
    common_parameters = {
        "principal": sentinel.principal,
        "deposit_account": sentinel.deposit_account,
        "denomination": sentinel.denomination,
    }

    @patch.object(mortgage.declining_principal, "AmortisationFeature")
    @patch.object(mortgage.fixed_to_variable, "InterestRate")
    @patch.object(mortgage.overpayment_allowance, "scheduled_events")
    @patch.object(mortgage.emi, "amortise")
    @patch.object(mortgage.disbursement, "get_disbursement_custom_instruction")
    @patch.object(
        mortgage.overpayment_allowance, "initialise_overpayment_allowance_from_principal_amount"
    )
    @patch.object(mortgage.utils, "get_schedule_expression_from_parameters")
    @patch.object(mortgage.due_amount_calculation, "scheduled_events")
    @patch.object(mortgage.interest_accrual, "scheduled_events")
    @patch.object(mortgage.utils, "get_parameter")
    def test_schedules_and_pi_directives_correct_on_activation_no_interest_only_term(
        self,
        mock_get_parameter: MagicMock,
        mock_accrual_scheduled_events: MagicMock,
        mock_due_amount_scheduled_events: MagicMock,
        mock_get_schedule_expression_from_parameters: MagicMock,
        mock_initialise_overpayment_allowance_from_principal_amount: MagicMock,
        mock_get_disbursement_custom_instruction: MagicMock,
        mock_emi_amortise: MagicMock,
        mock_overpayment_allowance_due_amount_scheduled_events: MagicMock,
        mock_fixed_to_variable_rate: MagicMock,
        mock_declining_principal_amortisation: MagicMock,
    ):
        # Expected values
        start_datetime = DEFAULT_DATETIME + relativedelta(days=1)
        accrual_scheduled_event = {
            sentinel.accrual_event_type: SentinelScheduledEvent("accrual_event")
        }
        due_amount_scheduled_event = {
            sentinel.due_amount_event_type: SentinelScheduledEvent("due_amount_event")
        }
        overpayment_allowance_scheduled_event = {
            sentinel.overpayment_allowance_event_type: SentinelScheduledEvent(
                "overpayment_allowance_event"
            )
        }

        check_delinquency_scheduled_event = {
            mortgage.CHECK_DELINQUENCY: ScheduledEvent(
                skip=True,
                start_datetime=start_datetime,
                expression=SentinelScheduleExpression("check_delinquency_event"),
            )
        }

        # Set mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={**self.common_parameters, "interest_only_term": "0"}
        )
        mock_accrual_scheduled_events.return_value = accrual_scheduled_event
        mock_due_amount_scheduled_events.return_value = due_amount_scheduled_event
        mock_overpayment_allowance_due_amount_scheduled_events.return_value = (
            overpayment_allowance_scheduled_event
        )
        mock_get_schedule_expression_from_parameters.side_effect = [
            SentinelScheduleExpression("check_delinquency_event"),
        ]
        mock_get_disbursement_custom_instruction.return_value = [
            SentinelCustomInstruction("disbursement")
        ]
        mock_initialise_overpayment_allowance_from_principal_amount.return_value = [
            SentinelCustomInstruction("overpayment_allowance")
        ]
        mock_emi_amortise.return_value = [SentinelCustomInstruction("emi")]

        mock_vault = self.create_mock()

        hook_args = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        hook_result = mortgage.activation_hook(vault=mock_vault, hook_arguments=hook_args)
        scheduled_events = hook_result.scheduled_events_return_value  # type: ignore
        pi_directives = hook_result.posting_instructions_directives  # type: ignore

        self.assertEqual(
            scheduled_events,
            {
                **accrual_scheduled_event,
                **due_amount_scheduled_event,
                **overpayment_allowance_scheduled_event,
                **check_delinquency_scheduled_event,
            },
        )
        self.assertEqual(
            pi_directives[0].posting_instructions,
            [
                SentinelCustomInstruction("disbursement"),
                SentinelCustomInstruction("overpayment_allowance"),
                SentinelCustomInstruction("emi"),
            ],
        )
        mock_accrual_scheduled_events.assert_called_once_with(
            mock_vault, start_datetime=start_datetime
        )
        mock_due_amount_scheduled_events.assert_called_once_with(
            mock_vault, account_opening_datetime=DEFAULT_DATETIME
        )
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            mock_vault,
            parameter_prefix=mortgage.CHECK_DELINQUENCY_PREFIX,
        )
        mock_get_disbursement_custom_instruction.assert_called_once_with(
            account_id=mock_vault.account_id,
            deposit_account_id=sentinel.deposit_account,
            principal=sentinel.principal,
            denomination=sentinel.denomination,
        )
        mock_initialise_overpayment_allowance_from_principal_amount(
            vault=mock_vault, principal=sentinel.principal, denomination=sentinel.denomination
        )
        mock_emi_amortise.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=mock_declining_principal_amortisation,
            interest_calculation_feature=mock_fixed_to_variable_rate,
        )

    @patch.object(mortgage.overpayment_allowance, "scheduled_events")
    @patch.object(mortgage.emi, "amortise")
    @patch.object(mortgage.disbursement, "get_disbursement_custom_instruction")
    @patch.object(
        mortgage.overpayment_allowance, "initialise_overpayment_allowance_from_principal_amount"
    )
    @patch.object(mortgage.utils, "get_schedule_expression_from_parameters")
    @patch.object(mortgage.due_amount_calculation, "scheduled_events")
    @patch.object(mortgage.interest_accrual, "scheduled_events")
    @patch.object(mortgage.utils, "get_parameter")
    def test_schedules_and_pi_directives_correct_on_activation_with_interest_only_term(
        self,
        mock_get_parameter: MagicMock,
        mock_accrual_scheduled_events: MagicMock,
        mock_due_amount_scheduled_events: MagicMock,
        mock_get_schedule_expression_from_parameters: MagicMock,
        mock_initialise_overpayment_allowance_from_principal_amount: MagicMock,
        mock_get_disbursement_custom_instruction: MagicMock,
        mock_emi_amortise: MagicMock,
        mock_overpayment_allowance_due_amount_scheduled_events: MagicMock,
    ):
        # Expected values
        start_datetime = DEFAULT_DATETIME + relativedelta(days=1)
        accrual_scheduled_event = {
            sentinel.accrual_event_type: SentinelScheduledEvent("accrual_event")
        }
        due_amount_scheduled_event = {
            sentinel.due_amount_event_type: SentinelScheduledEvent("due_amount_event")
        }
        overpayment_allowance_scheduled_event = {
            sentinel.overpayment_allowance_event_type: SentinelScheduledEvent(
                "overpayment_allowance_event"
            )
        }

        check_delinquency_scheduled_event = {
            mortgage.CHECK_DELINQUENCY: ScheduledEvent(
                skip=True,
                start_datetime=start_datetime,
                expression=SentinelScheduleExpression("check_delinquency_event"),
            )
        }

        # Set mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={**self.common_parameters, "interest_only_term": "1"}
        )
        mock_accrual_scheduled_events.return_value = accrual_scheduled_event
        mock_due_amount_scheduled_events.return_value = due_amount_scheduled_event
        mock_overpayment_allowance_due_amount_scheduled_events.return_value = (
            overpayment_allowance_scheduled_event
        )
        mock_get_schedule_expression_from_parameters.side_effect = [
            SentinelScheduleExpression("check_delinquency_event"),
        ]
        mock_get_disbursement_custom_instruction.return_value = [
            SentinelCustomInstruction("disbursement")
        ]
        mock_initialise_overpayment_allowance_from_principal_amount.return_value = [
            SentinelCustomInstruction("overpayment_allowance")
        ]

        mock_vault = self.create_mock()

        hook_args = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        hook_result = mortgage.activation_hook(vault=mock_vault, hook_arguments=hook_args)
        scheduled_events = hook_result.scheduled_events_return_value  # type: ignore
        pi_directives = hook_result.posting_instructions_directives  # type: ignore

        self.assertEqual(
            scheduled_events,
            {
                **accrual_scheduled_event,
                **due_amount_scheduled_event,
                **overpayment_allowance_scheduled_event,
                **check_delinquency_scheduled_event,
            },
        )
        self.assertEqual(
            pi_directives[0].posting_instructions,
            [
                SentinelCustomInstruction("disbursement"),
                SentinelCustomInstruction("overpayment_allowance"),
            ],
        )
        mock_accrual_scheduled_events.assert_called_once_with(
            mock_vault, start_datetime=start_datetime
        )
        mock_due_amount_scheduled_events.assert_called_once_with(
            mock_vault, account_opening_datetime=DEFAULT_DATETIME
        )
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            mock_vault,
            parameter_prefix=mortgage.CHECK_DELINQUENCY_PREFIX,
        )
        mock_get_disbursement_custom_instruction.assert_called_once_with(
            account_id=mock_vault.account_id,
            deposit_account_id=sentinel.deposit_account,
            principal=sentinel.principal,
            denomination=sentinel.denomination,
        )
        mock_initialise_overpayment_allowance_from_principal_amount(
            vault=mock_vault, principal=sentinel.principal, denomination=sentinel.denomination
        )
        mock_emi_amortise.assert_not_called()
