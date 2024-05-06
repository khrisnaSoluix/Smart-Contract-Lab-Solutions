# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel
from zoneinfo import ZoneInfo

# library
from library.bnpl.contracts.template import bnpl
from library.bnpl.test.unit.test_bnpl_common import BNPLTest

# features
import library.features.v4.common.events as events
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import ActivationHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DATETIME,
    DEFAULT_DENOMINATION,
    DEFAULT_HOOK_EXECUTION_ID,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    ActivationHookResult,
    CustomInstruction,
    PostingInstructionsDirective,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    DEFAULT_POSTINGS,
    SentinelCustomInstruction,
    SentinelScheduledEvent,
)


@patch.object(bnpl.due_amount_notification, "scheduled_events")
@patch.object(bnpl.delinquency, "scheduled_events")
@patch.object(bnpl.late_repayment, "scheduled_events")
@patch.object(bnpl.overdue, "scheduled_events")
@patch.object(bnpl.config_repayment_frequency, "get_due_amount_calculation_schedule")
@patch.object(
    bnpl.disbursement,
    "get_disbursement_custom_instruction",
    MagicMock(return_value=[SentinelCustomInstruction("disbursement")]),
)
@patch.object(bnpl.emi_in_advance, "charge")
@patch.object(bnpl.utils, "get_parameter")
@patch.object(
    bnpl.due_amount_calculation,
    "update_due_amount_calculation_counter",
    MagicMock(return_value=DEFAULT_POSTINGS),
)
class ActivationHookTest(BNPLTest):
    default_principal_amount = Decimal("100000")
    default_deposit_account = sentinel.default_deposit_account
    monthly = bnpl.config_repayment_frequency.MONTHLY
    grace_period = 2
    repayment_period = 1
    total_repayment_count = 5

    common_param_return_vals = {
        bnpl.common_parameters.PARAM_DENOMINATION: DEFAULT_DENOMINATION,
        bnpl.disbursement.PARAM_PRINCIPAL: default_principal_amount,
        bnpl.disbursement.PARAM_DEPOSIT_ACCOUNT: default_deposit_account,
        bnpl.overdue.PARAM_REPAYMENT_PERIOD: repayment_period,
        bnpl.delinquency.PARAM_GRACE_PERIOD: grace_period,
        bnpl.config_repayment_frequency.PARAM_REPAYMENT_FREQUENCY: monthly,
        bnpl.lending_params.PARAM_TOTAL_REPAYMENT_COUNT: total_repayment_count,
    }

    def test_feature_instructions(
        self,
        mock_get_parameter: MagicMock,
        mock_charge: MagicMock,
        mock_get_due_amount_calculation_schedule: MagicMock,
        mock_overdue_scheduled_events: MagicMock,
        mock_late_repayment_scheduled_events: MagicMock,
        mock_delinquency_scheduled_events: MagicMock,
        mock_due_amount_notification_scheduled_events: MagicMock,
    ):
        # expected values
        disbursement_custom_instructions = [SentinelCustomInstruction("disbursement")]
        update_counter_postings = DEFAULT_POSTINGS
        update_counter_custom_instructions = [
            CustomInstruction(
                postings=update_counter_postings,
                instruction_details={
                    "description": "Update due amount calculation counter on account activation",
                    "event": events.ACCOUNT_ACTIVATION,
                },
            )
        ]
        charge_custom_instructions = [SentinelCustomInstruction(f"charge_{i}") for i in range(2)]

        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                **self.common_param_return_vals,
            },
        )
        mock_vault = self.create_mock()
        mock_charge.return_value = charge_custom_instructions
        mock_get_due_amount_calculation_schedule.return_value = {}
        mock_overdue_scheduled_events.return_value = {}
        mock_late_repayment_scheduled_events.return_value = {}
        mock_delinquency_scheduled_events.return_value = {}
        mock_due_amount_notification_scheduled_events.return_value = {}

        # construct expected result
        full_pi = (
            disbursement_custom_instructions
            + charge_custom_instructions
            + update_counter_custom_instructions
        )
        expected = ActivationHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=full_pi,  # type: ignore
                    client_batch_id=f"{events.ACCOUNT_ACTIVATION}_{DEFAULT_HOOK_EXECUTION_ID}",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
        )

        # run function
        hook_args = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        res = bnpl.activation_hook(mock_vault, hook_arguments=hook_args)

        # validate results
        self.assertEqual(expected, res)
        mock_charge.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=bnpl.declining_principal.AmortisationFeature,
        )

    def test_monthly_schedules(
        self,
        mock_get_parameter: MagicMock,
        mock_charge: MagicMock,
        mock_get_due_amount_calculation_schedule: MagicMock,
        mock_overdue_scheduled_events: MagicMock,
        mock_late_repayment_scheduled_events: MagicMock,
        mock_delinquency_scheduled_events: MagicMock,
        mock_due_amount_notification_scheduled_events: MagicMock,
    ):
        # expected values
        update_counter_postings = DEFAULT_POSTINGS
        sched_due = {
            bnpl.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: SentinelScheduledEvent(
                bnpl.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT
            ),
        }
        sched_overdue = {
            bnpl.overdue.CHECK_OVERDUE_EVENT: SentinelScheduledEvent(
                bnpl.overdue.CHECK_OVERDUE_EVENT
            ),
        }
        sched_late_repayment = {
            bnpl.late_repayment.CHECK_LATE_REPAYMENT_EVENT: SentinelScheduledEvent(
                bnpl.late_repayment.CHECK_LATE_REPAYMENT_EVENT
            ),
        }
        sched_delinquency = {
            bnpl.delinquency.CHECK_DELINQUENCY_EVENT: SentinelScheduledEvent(
                bnpl.delinquency.CHECK_DELINQUENCY_EVENT
            ),
        }
        update_counter_custom_instructions = [
            CustomInstruction(
                postings=update_counter_postings,  # type: ignore
                instruction_details={
                    "description": "Update due amount calculation counter on account activation",
                    "event": events.ACCOUNT_ACTIVATION,
                },
            )
        ]
        sched_due_amount_notification = {
            bnpl.due_amount_notification.NOTIFY_DUE_AMOUNT_EVENT: SentinelScheduledEvent(
                bnpl.due_amount_notification.NOTIFY_DUE_AMOUNT_EVENT
            ),
        }

        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                **self.common_param_return_vals,
            },
        )
        mock_charge.return_value = []
        mock_get_due_amount_calculation_schedule.return_value = sched_due
        mock_overdue_scheduled_events.return_value = sched_overdue
        mock_late_repayment_scheduled_events.return_value = sched_late_repayment
        mock_delinquency_scheduled_events.return_value = sched_delinquency
        mock_due_amount_notification_scheduled_events.return_value = sched_due_amount_notification
        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATETIME,
        )

        # construct expected result
        expected = ActivationHookResult(
            scheduled_events_return_value=dict(
                **sched_due,
                **sched_overdue,
                **sched_late_repayment,
                **sched_delinquency,
                **sched_due_amount_notification,
            ),
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[SentinelCustomInstruction("disbursement")]
                    + update_counter_custom_instructions,  # type: ignore
                    client_batch_id=f"{events.ACCOUNT_ACTIVATION}_{DEFAULT_HOOK_EXECUTION_ID}",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
        )
        # run function
        hook_args = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        res = bnpl.activation_hook(mock_vault, hook_arguments=hook_args)
        # validate results
        self.assertEqual(expected, res)
        mock_get_due_amount_calculation_schedule.assert_called_once_with(
            vault=mock_vault,
            first_due_amount_calculation_datetime=DEFAULT_DATETIME + relativedelta(months=1),
            repayment_frequency="monthly",
        )
        mock_overdue_scheduled_events.assert_called_once_with(
            vault=mock_vault,
            first_due_amount_calculation_datetime=DEFAULT_DATETIME,
        )
        mock_late_repayment_scheduled_events.assert_called_once_with(
            vault=mock_vault,
            start_datetime=DEFAULT_DATETIME
            + relativedelta(days=self.grace_period + self.repayment_period),
            skip=False,
        )
        mock_delinquency_scheduled_events.assert_called_once_with(
            vault=mock_vault,
            start_datetime=datetime(2019, 5, 4, 0, 0, tzinfo=ZoneInfo("UTC")),
            is_one_off=True,
        )
        mock_due_amount_notification_scheduled_events.assert_called_once_with(
            vault=mock_vault,
            next_due_amount_calc_datetime=DEFAULT_DATETIME + relativedelta(months=1),
        )
        mock_charge.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=bnpl.declining_principal.AmortisationFeature,
        )

    def test_weekly_schedules(
        self,
        mock_get_parameter: MagicMock,
        mock_charge: MagicMock,
        mock_get_due_amount_calculation_schedule: MagicMock,
        mock_overdue_scheduled_events: MagicMock,
        mock_late_repayment_scheduled_events: MagicMock,
        mock_delinquency_scheduled_events: MagicMock,
        mock_due_amount_notification_scheduled_events: MagicMock,
    ):
        # expected values
        weekly = bnpl.config_repayment_frequency.WEEKLY
        sched_due = {
            bnpl.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: SentinelScheduledEvent(
                bnpl.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT
            ),
        }
        update_counter_postings = DEFAULT_POSTINGS
        update_counter_custom_instructions = [
            CustomInstruction(
                postings=update_counter_postings,  # type: ignore
                instruction_details={
                    "description": "Update due amount calculation counter on account activation",
                    "event": events.ACCOUNT_ACTIVATION,
                },
            )
        ]
        sched_delinquency = {
            bnpl.delinquency.CHECK_DELINQUENCY_EVENT: SentinelScheduledEvent(
                bnpl.delinquency.CHECK_DELINQUENCY_EVENT
            ),
        }
        sched_overdue = {
            bnpl.overdue.CHECK_OVERDUE_EVENT: SentinelScheduledEvent(
                bnpl.overdue.CHECK_OVERDUE_EVENT
            ),
        }
        sched_late_repayment = {
            bnpl.late_repayment.CHECK_LATE_REPAYMENT_EVENT: SentinelScheduledEvent(
                bnpl.late_repayment.CHECK_LATE_REPAYMENT_EVENT
            ),
        }
        sched_due_amount_notification = {
            bnpl.due_amount_notification.NOTIFY_DUE_AMOUNT_EVENT: SentinelScheduledEvent(
                bnpl.due_amount_notification.NOTIFY_DUE_AMOUNT_EVENT
            ),
        }

        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                **self.common_param_return_vals,
                bnpl.config_repayment_frequency.PARAM_REPAYMENT_FREQUENCY: weekly,
            },
        )
        mock_charge.return_value = []
        mock_get_due_amount_calculation_schedule.return_value = sched_due
        mock_overdue_scheduled_events.return_value = sched_overdue
        mock_late_repayment_scheduled_events.return_value = sched_late_repayment
        mock_delinquency_scheduled_events.return_value = sched_delinquency
        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATETIME,
        )
        mock_due_amount_notification_scheduled_events.return_value = sched_due_amount_notification

        # construct expected result
        expected = ActivationHookResult(
            scheduled_events_return_value=dict(
                **sched_due,
                **sched_overdue,
                **sched_late_repayment,
                **sched_delinquency,
                **sched_due_amount_notification,
            ),
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[SentinelCustomInstruction("disbursement")]
                    + update_counter_custom_instructions,  # type: ignore
                    client_batch_id=f"{events.ACCOUNT_ACTIVATION}_{DEFAULT_HOOK_EXECUTION_ID}",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
        )
        # run function
        hook_args = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        res = bnpl.activation_hook(mock_vault, hook_arguments=hook_args)
        # validate results
        self.assertEqual(expected, res)
        mock_get_due_amount_calculation_schedule.assert_called_once_with(
            vault=mock_vault,
            first_due_amount_calculation_datetime=DEFAULT_DATETIME + relativedelta(weeks=1),
            repayment_frequency="weekly",
        )
        mock_overdue_scheduled_events.assert_called_once_with(
            vault=mock_vault,
            first_due_amount_calculation_datetime=DEFAULT_DATETIME,
        )
        mock_late_repayment_scheduled_events.assert_called_once_with(
            vault=mock_vault,
            start_datetime=DEFAULT_DATETIME
            + relativedelta(days=self.grace_period + self.repayment_period),
            skip=False,
        )
        mock_delinquency_scheduled_events.assert_called_once_with(
            vault=mock_vault,
            start_datetime=datetime(2019, 2, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
            is_one_off=True,
        )
        mock_due_amount_notification_scheduled_events.assert_called_once_with(
            vault=mock_vault,
            next_due_amount_calc_datetime=DEFAULT_DATETIME + relativedelta(weeks=1),
        )
        mock_charge.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=bnpl.declining_principal.AmortisationFeature,
        )

    def test_fortnightly_schedules(
        self,
        mock_get_parameter: MagicMock,
        mock_charge: MagicMock,
        mock_get_due_amount_calculation_schedule: MagicMock,
        mock_overdue_scheduled_events: MagicMock,
        mock_late_repayment_scheduled_events: MagicMock,
        mock_delinquency_scheduled_events: MagicMock,
        mock_due_amount_notification_scheduled_events: MagicMock,
    ):
        # expected values
        fortnightly = bnpl.config_repayment_frequency.FORTNIGHTLY
        sched_due = {
            bnpl.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: SentinelScheduledEvent(
                bnpl.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT
            ),
        }
        update_counter_postings = DEFAULT_POSTINGS
        update_counter_custom_instructions = [
            CustomInstruction(
                postings=update_counter_postings,  # type: ignore
                instruction_details={
                    "description": "Update due amount calculation counter on account activation",
                    "event": events.ACCOUNT_ACTIVATION,
                },
            )
        ]
        sched_overdue = {
            bnpl.overdue.CHECK_OVERDUE_EVENT: SentinelScheduledEvent(
                bnpl.overdue.CHECK_OVERDUE_EVENT
            ),
        }
        sched_late_repayment = {
            bnpl.late_repayment.CHECK_LATE_REPAYMENT_EVENT: SentinelScheduledEvent(
                bnpl.late_repayment.CHECK_LATE_REPAYMENT_EVENT
            ),
        }
        sched_delinquency = {
            bnpl.delinquency.CHECK_DELINQUENCY_EVENT: SentinelScheduledEvent(
                bnpl.delinquency.CHECK_DELINQUENCY_EVENT
            ),
        }
        sched_due_amount_notification = {
            bnpl.due_amount_notification.NOTIFY_DUE_AMOUNT_EVENT: SentinelScheduledEvent(
                bnpl.due_amount_notification.NOTIFY_DUE_AMOUNT_EVENT
            ),
        }

        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                **self.common_param_return_vals,
                bnpl.config_repayment_frequency.PARAM_REPAYMENT_FREQUENCY: fortnightly,
            },
        )
        mock_charge.return_value = []
        mock_get_due_amount_calculation_schedule.return_value = sched_due
        mock_overdue_scheduled_events.return_value = sched_overdue
        mock_late_repayment_scheduled_events.return_value = sched_late_repayment
        mock_delinquency_scheduled_events.return_value = sched_delinquency
        mock_due_amount_notification_scheduled_events.return_value = sched_due_amount_notification
        mock_vault = self.create_mock(creation_date=DEFAULT_DATETIME)

        # construct expected result

        expected = ActivationHookResult(
            scheduled_events_return_value=dict(
                **sched_due,
                **sched_overdue,
                **sched_late_repayment,
                **sched_delinquency,
                **sched_due_amount_notification,
            ),
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[SentinelCustomInstruction("disbursement")]
                    + update_counter_custom_instructions,  # type: ignore
                    client_batch_id=f"{events.ACCOUNT_ACTIVATION}_{DEFAULT_HOOK_EXECUTION_ID}",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
        )

        # run function
        hook_args = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        res = bnpl.activation_hook(mock_vault, hook_arguments=hook_args)

        # validate results
        self.assertEqual(expected, res)
        mock_get_due_amount_calculation_schedule.assert_called_once_with(
            vault=mock_vault,
            first_due_amount_calculation_datetime=DEFAULT_DATETIME + relativedelta(weeks=2),
            repayment_frequency="fortnightly",
        )
        mock_overdue_scheduled_events.assert_called_once_with(
            vault=mock_vault,
            first_due_amount_calculation_datetime=DEFAULT_DATETIME,
        )
        mock_late_repayment_scheduled_events.assert_called_once_with(
            vault=mock_vault,
            start_datetime=DEFAULT_DATETIME
            + relativedelta(days=self.grace_period + self.repayment_period),
            skip=False,
        )
        mock_delinquency_scheduled_events.assert_called_once_with(
            vault=mock_vault,
            start_datetime=datetime(2019, 3, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
            is_one_off=True,
        )
        mock_due_amount_notification_scheduled_events.assert_called_once_with(
            vault=mock_vault,
            next_due_amount_calc_datetime=DEFAULT_DATETIME + relativedelta(weeks=2),
        )
        mock_charge.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=bnpl.declining_principal.AmortisationFeature,
        )

    def test_no_grace_period(
        self,
        mock_get_parameter: MagicMock,
        mock_charge: MagicMock,
        mock_get_due_amount_calculation_schedule: MagicMock,
        mock_overdue_scheduled_events: MagicMock,
        mock_late_repayment_scheduled_events: MagicMock,
        mock_delinquency_scheduled_events: MagicMock,
        mock_due_amount_notification_scheduled_events: MagicMock,
    ):
        # expected values
        update_counter_postings = DEFAULT_POSTINGS
        update_counter_custom_instructions = [
            CustomInstruction(
                postings=update_counter_postings,  # type: ignore
                instruction_details={
                    "description": "Update due amount calculation counter on account activation",
                    "event": events.ACCOUNT_ACTIVATION,
                },
            )
        ]
        sched_due = {
            bnpl.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: SentinelScheduledEvent(
                bnpl.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT
            ),
        }
        sched_overdue = {
            bnpl.overdue.CHECK_OVERDUE_EVENT: SentinelScheduledEvent(
                bnpl.overdue.CHECK_OVERDUE_EVENT
            ),
        }
        sched_late_repayment = {
            bnpl.late_repayment.CHECK_LATE_REPAYMENT_EVENT: SentinelScheduledEvent(
                bnpl.late_repayment.CHECK_LATE_REPAYMENT_EVENT
            ),
        }
        sched_delinquency = {
            bnpl.delinquency.CHECK_DELINQUENCY_EVENT: SentinelScheduledEvent(
                bnpl.delinquency.CHECK_DELINQUENCY_EVENT
            ),
        }

        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={**self.common_param_return_vals, bnpl.delinquency.PARAM_GRACE_PERIOD: 0},
        )
        mock_charge.return_value = []
        mock_get_due_amount_calculation_schedule.return_value = sched_due
        mock_overdue_scheduled_events.return_value = sched_overdue
        mock_due_amount_notification_scheduled_events.return_value = {}
        mock_late_repayment_scheduled_events.return_value = sched_late_repayment
        mock_delinquency_scheduled_events.return_value = sched_delinquency
        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATETIME,
        )
        # construct expected result
        expected = ActivationHookResult(
            scheduled_events_return_value=dict(
                **sched_due,
                **sched_overdue,
                **sched_late_repayment,
                **sched_delinquency,
            ),
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[SentinelCustomInstruction("disbursement")]
                    + update_counter_custom_instructions,  # type: ignore
                    client_batch_id=f"{events.ACCOUNT_ACTIVATION}_{DEFAULT_HOOK_EXECUTION_ID}",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
        )
        # run function
        hook_args = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        res = bnpl.activation_hook(mock_vault, hook_arguments=hook_args)
        # validate results
        self.assertEqual(expected, res)
        mock_get_due_amount_calculation_schedule.assert_called_once_with(
            vault=mock_vault,
            first_due_amount_calculation_datetime=DEFAULT_DATETIME + relativedelta(months=1),
            repayment_frequency="monthly",
        )
        mock_overdue_scheduled_events.assert_called_once_with(
            vault=mock_vault,
            first_due_amount_calculation_datetime=DEFAULT_DATETIME,
        )
        mock_late_repayment_scheduled_events.assert_called_once_with(
            vault=mock_vault,
            start_datetime=DEFAULT_DATETIME + relativedelta(days=self.repayment_period),
            skip=True,
        )
        mock_delinquency_scheduled_events.assert_called_once_with(
            vault=mock_vault,
            start_datetime=datetime(2019, 5, 2, 0, 0, tzinfo=ZoneInfo("UTC")),
            is_one_off=True,
        )
        mock_charge.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=bnpl.declining_principal.AmortisationFeature,
        )
