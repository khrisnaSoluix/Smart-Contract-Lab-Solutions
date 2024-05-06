# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs

# standard libs
from collections import defaultdict
from datetime import datetime
from dateutil.relativedelta import relativedelta
from unittest.mock import ANY, MagicMock, patch, sentinel
from zoneinfo import ZoneInfo

# library
from library.credit_card.contracts.template import credit_card
from library.credit_card.test.unit.test_credit_card_common import CreditCardTestBase

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import ScheduledEventHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    BalanceCoordinate,
    BalanceDefaultDict,
    BalanceTimeseries,
    Phase,
    PostingInstructionsDirective,
    ScheduledEventHookResult,
    UpdateAccountEventTypeDirective,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelAccountNotificationDirective,
    SentinelBalance,
    SentinelCustomInstruction,
    SentinelPostingInstructionsDirective,
    SentinelScheduleExpression,
)

DEFAULT_COORDINATE = BalanceCoordinate(DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.COMMITTED)


class AnnualFeeScheduledEventTest(CreditCardTestBase):
    def test_schedule_with_dummy_event_type(self):
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type="DUMMY"
        )
        result = credit_card.scheduled_event_hook(vault=sentinel.vault, hook_arguments=hook_args)

        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[],
            update_account_event_type_directives=[],
            account_notification_directives=[],
        )

        self.assertEqual(result, expected_result)

    @patch.object(credit_card.utils, "get_schedule_expression_from_parameters")
    @patch.object(credit_card, "_charge_annual_fee")
    def test_annual_fee_no_fee_pi_directives_returned(
        self,
        mock_charge_annual_fee: MagicMock,
        mock_get_schedule_expression_from_parameters: MagicMock,
    ):
        # Construct mocks
        mock_vault = self.create_mock()
        mock_charge_annual_fee.return_value = []
        mock_get_schedule_expression_from_parameters.side_effect = [
            SentinelScheduleExpression("annual_fee")
        ]

        # Construct expected result
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[],
            update_account_event_type_directives=[
                UpdateAccountEventTypeDirective(
                    event_type="ANNUAL_FEE", expression=SentinelScheduleExpression("annual_fee")
                ),
            ],
            account_notification_directives=[],
        )

        # Run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type="ANNUAL_FEE"
        )
        result = credit_card.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)

        # Assert calls
        mock_charge_annual_fee.assert_called_with(mock_vault, DEFAULT_DATETIME)
        mock_get_schedule_expression_from_parameters.assert_called_with(
            mock_vault,
            credit_card.ANNUAL_FEE_SCHEDULE_PREFIX,
            day=str(mock_vault.get_account_creation_datetime().day),
            month=str(mock_vault.get_account_creation_datetime().month),
            year=str(DEFAULT_DATETIME.year + 1),
        )

    @patch.object(credit_card.utils, "get_schedule_expression_from_parameters")
    @patch.object(credit_card, "_charge_annual_fee")
    def test_posting_instruction_directive_for_annual_fee(
        self,
        mock_charge_annual_fee: MagicMock,
        mock_get_schedule_expression_from_parameters: MagicMock,
    ):
        # Construct mocks
        mock_vault = self.create_mock()
        mock_charge_annual_fee.return_value = [
            PostingInstructionsDirective(
                posting_instructions=[SentinelCustomInstruction("annual_fee")],
                client_batch_id=f"ANNUAL_FEE-{mock_vault.get_hook_execution_id()}",
            )
        ]
        mock_get_schedule_expression_from_parameters.side_effect = [
            SentinelScheduleExpression("annual_fee")
        ]

        # Construct expected result
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[SentinelCustomInstruction("annual_fee")],
                    client_batch_id=f"ANNUAL_FEE-{mock_vault.get_hook_execution_id()}",
                )
            ],
            update_account_event_type_directives=[
                UpdateAccountEventTypeDirective(
                    event_type="ANNUAL_FEE", expression=SentinelScheduleExpression("annual_fee")
                ),
            ],
            account_notification_directives=[],
        )

        # Run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type="ANNUAL_FEE"
        )
        result = credit_card.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)

        # Assert calls
        mock_get_schedule_expression_from_parameters.assert_called_with(
            mock_vault,
            credit_card.ANNUAL_FEE_SCHEDULE_PREFIX,
            day=str(mock_vault.get_account_creation_datetime().day),
            month=str(mock_vault.get_account_creation_datetime().month),
            year=str(DEFAULT_DATETIME.year + 1),
        )

    @patch.object(credit_card.utils, "get_schedule_expression_from_parameters")
    @patch.object(credit_card, "_charge_annual_fee")
    def test_posting_instruction_directive_for_annual_fee_creation_date_feb_29(
        self,
        mock_charge_annual_fee: MagicMock,
        mock_get_schedule_expression_from_parameters: MagicMock,
    ):
        # Construct mocks
        mock_vault = self.create_mock(creation_date=datetime(2020, 2, 29, tzinfo=ZoneInfo("UTC")))
        mock_charge_annual_fee.return_value = [
            PostingInstructionsDirective(
                posting_instructions=[SentinelCustomInstruction("annual_fee")],
                client_batch_id=f"ANNUAL_FEE-{mock_vault.get_hook_execution_id()}",
            )
        ]
        mock_get_schedule_expression_from_parameters.side_effect = [
            SentinelScheduleExpression("annual_fee")
        ]

        # Construct expected result
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[SentinelCustomInstruction("annual_fee")],
                    client_batch_id=f"ANNUAL_FEE-{mock_vault.get_hook_execution_id()}",
                )
            ],
            update_account_event_type_directives=[
                UpdateAccountEventTypeDirective(
                    event_type="ANNUAL_FEE", expression=SentinelScheduleExpression("annual_fee")
                ),
            ],
            account_notification_directives=[],
        )

        # Run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type="ANNUAL_FEE"
        )
        result = credit_card.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)

        # Assert calls
        mock_get_schedule_expression_from_parameters.assert_called_with(
            mock_vault,
            credit_card.ANNUAL_FEE_SCHEDULE_PREFIX,
            day="last",
            month=str(mock_vault.get_account_creation_datetime().month),
            year=str(DEFAULT_DATETIME.year + 1),
        )


class CreditCardPaymentDueDateTests(CreditCardTestBase):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = self.create_mock()

        # process payment due date
        patch_process_payment_due_date = patch.object(credit_card, "_process_payment_due_date")
        self.mock_process_payment_due_date = patch_process_payment_due_date.start()
        self.mock_process_payment_due_date.return_value = (
            [SentinelPostingInstructionsDirective("pdd")],
            [SentinelAccountNotificationDirective("pdd")],
        )

        # get parameter
        patch_get_parameter = patch.object(credit_card.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={credit_card.PARAM_PAYMENT_DUE_PERIOD: "1"}
        )

        # get next pdd
        self.local_next_pdd_start = SentinelScheduleExpression("local_next_pdd_start")
        self.local_next_pdd_end = SentinelScheduleExpression("local_next_pdd_end")
        patch_get_next_pdd = patch.object(credit_card, "_get_next_pdd")
        self.mock_get_next_pdd = patch_get_next_pdd.start()
        self.mock_get_next_pdd.return_value = (
            self.local_next_pdd_start,
            self.local_next_pdd_end,
        )

        # get scod for pdd
        self.local_next_scod_start = DEFAULT_DATETIME + relativedelta(months=1)
        self.local_next_scod_end = DEFAULT_DATETIME + relativedelta(months=1, seconds=1)
        patch_get_scod_for_pdd = patch.object(credit_card, "_get_scod_for_pdd")
        self.mock_get_scod_for_pdd = patch_get_scod_for_pdd.start()
        self.mock_get_scod_for_pdd.return_value = (
            self.local_next_scod_start,
            self.local_next_scod_end,
        )

        # get schedule expression from parameters
        patch_get_schedule_expression_from_parameters = patch.object(
            credit_card.utils, "get_schedule_expression_from_parameters"
        )
        self.mock_get_schedule_expression_from_parameters = (
            patch_get_schedule_expression_from_parameters.start()
        )
        self.mock_get_schedule_expression_from_parameters.return_value = SentinelScheduleExpression(
            "scod_schedule_expression"
        )

        #  default hook arguments
        self.hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=credit_card.EVENT_PDD,
        )

        # tear down of patches
        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_schedule_with_dummy_event_type(self):
        # construct hook arguments
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type="DUMMY"
        )

        # run hook
        result = credit_card.scheduled_event_hook(vault=sentinel.vault, hook_arguments=hook_args)

        # construct expected result
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[],
            update_account_event_type_directives=[],
            account_notification_directives=[],
        )

        # assert result
        self.assertEqual(result, expected_result)

    def test_payment_due_date_pi_directives_returned(self):
        # run hook
        result = credit_card.scheduled_event_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        # construct expected result
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[SentinelPostingInstructionsDirective("pdd")],
            account_notification_directives=[SentinelAccountNotificationDirective("pdd")],
            update_account_event_type_directives=[
                UpdateAccountEventTypeDirective(
                    event_type=credit_card.EVENT_SCOD,
                    expression=self.mock_get_schedule_expression_from_parameters.return_value,
                )
            ],
        )

        # assert result
        self.assertEqual(result, expected_result)

        # assert calls
        self.mock_process_payment_due_date.assert_called_with(self.mock_vault, DEFAULT_DATETIME)

        self.mock_get_parameter.assert_called_with(
            name=credit_card.PARAM_PAYMENT_DUE_PERIOD,
            at_datetime=DEFAULT_DATETIME,
            vault=self.mock_vault,
        )

        self.mock_get_next_pdd.assert_called_with(
            1,
            DEFAULT_DATETIME,
            last_pdd_execution_datetime=DEFAULT_DATETIME,
        )

        self.mock_get_scod_for_pdd.assert_called_with(1, self.local_next_pdd_start)

        self.mock_get_schedule_expression_from_parameters.assert_called_with(
            self.mock_vault,
            credit_card.SCOD_SCHEDULE_PREFIX,
            day="1",
            month="2",
        )

    def test_payment_due_date_no_payment_due_pi_directives_returned(self):
        # update return value of processing payment due date to have no PI Directives
        self.mock_process_payment_due_date.return_value = (
            [],
            [SentinelAccountNotificationDirective("pdd")],
        )

        # run hook
        result = credit_card.scheduled_event_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        # construct expected result
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[],
            account_notification_directives=[SentinelAccountNotificationDirective("pdd")],
            update_account_event_type_directives=[
                UpdateAccountEventTypeDirective(
                    event_type=credit_card.EVENT_SCOD,
                    expression=self.mock_get_schedule_expression_from_parameters.return_value,
                )
            ],
        )

        # assert result
        self.assertEqual(result, expected_result)

        # assert calls
        self.mock_process_payment_due_date.assert_called_with(self.mock_vault, DEFAULT_DATETIME)

        self.mock_get_parameter.assert_called_with(
            name=credit_card.PARAM_PAYMENT_DUE_PERIOD,
            at_datetime=DEFAULT_DATETIME,
            vault=self.mock_vault,
        )

        self.mock_get_next_pdd.assert_called_with(
            1,
            DEFAULT_DATETIME,
            last_pdd_execution_datetime=DEFAULT_DATETIME,
        )

        self.mock_get_scod_for_pdd.assert_called_with(1, self.local_next_pdd_start)

        self.mock_get_schedule_expression_from_parameters.assert_called_with(
            self.mock_vault,
            credit_card.SCOD_SCHEDULE_PREFIX,
            day="1",
            month="2",
        )


class AccrueInterestScheduledEventTest(CreditCardTestBase):
    common_get_param_return_values: dict = {
        "denomination": "GBP",
        "transaction_types": {"purchase": {}, "cash_advance": {}, "transfer": {}},
        "interest_free_expiry": {
            "cash_advance": "2020-12-31 12:00:00",
            "purchase": "2020-12-31 12:00:00",
        },
        "transaction_interest_free_expiry": {"balance_transfer": {"REF1": "2020-12-31 12:00:00"}},
    }

    @patch.object(credit_card, "_process_interest_accrual_and_charging")
    def test_interest_accrual_with_accrual_instructions(
        self,
        mock_process_interest_accrual_and_charging: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock()

        accrual_ci_directive = [
            PostingInstructionsDirective(
                posting_instructions=[SentinelCustomInstruction("accrue_ci")],
                client_batch_id="CREDIT_CARD_ACCRUAL_EVENT_MOCK_HOOK",
                value_datetime=DEFAULT_DATETIME,
            )
        ]
        mock_process_interest_accrual_and_charging.return_value = accrual_ci_directive

        # construct expected result
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=accrual_ci_directive
        )

        # run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=credit_card.EVENT_ACCRUE
        )
        result = credit_card.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)

        # validate result
        self.assertEqual(result, expected_result)

    @patch.object(credit_card, "_process_interest_accrual_and_charging")
    def test_interest_accrual_with_no_accrual_instructions(
        self,
        mock_process_interest_accrual_and_charging: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock()

        accrual_ci_directive: list = []
        mock_process_interest_accrual_and_charging.return_value = accrual_ci_directive

        # construct expected result
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=accrual_ci_directive
        )

        # run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=credit_card.EVENT_ACCRUE
        )
        result = credit_card.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)

        # validate result
        self.assertEqual(result, expected_result)

    @patch.object(credit_card.utils, "is_flag_in_list_applied")
    @patch.object(credit_card, "_deep_copy_balances")
    @patch.object(credit_card.utils, "get_parameter")
    @patch.object(credit_card, "_get_supported_txn_types")
    @patch.object(credit_card, "_get_supported_fee_types")
    @patch.object(credit_card, "_is_revolver")
    @patch.object(credit_card, "_accrue_interest")
    @patch.object(credit_card, "_charge_interest")
    @patch.object(credit_card, "_adjust_aggregate_balances")
    def test_process_interest_accrual_and_charging_without_accrual_blocking_flag(
        self,
        mock_adjust_aggregate_balances: MagicMock,
        mock_charge_interest: MagicMock,
        mock_accrue_interest: MagicMock,
        mock_is_revolver: MagicMock,
        mock_get_supported_fee_types: MagicMock,
        mock_get_supported_txn_types: MagicMock,
        mock_get_parameter: MagicMock,
        mock_deep_copy_balances: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock()
        mock_is_flag_in_list_applied.return_value = False

        accrual_instructions = [SentinelCustomInstruction("accrual_instructions")]
        charge_interest_instructions = [SentinelCustomInstruction("charge_interest")]
        adjust_aggregate_balances_instructions = [
            SentinelCustomInstruction("adjust_aggregate_balances")
        ]

        start_of_period = datetime(2020, 1, 2, 3, 4, 5, 6, tzinfo=ZoneInfo("UTC"))
        effective_datetime = datetime(2020, 4, 5, 6, 7, 8, 9, tzinfo=ZoneInfo("UTC"))
        accrual_cut_off_dt = effective_datetime.replace(hour=0, minute=0, second=0) - relativedelta(
            microseconds=1
        )

        overpayment_balance_ts = BalanceTimeseries(
            [
                (start_of_period, SentinelBalance("start_of_period_overpayment")),
                (effective_datetime, SentinelBalance("effective_datetime_overpayment")),
            ]
        )
        balances_interval_fetchers_mapping = {
            credit_card.ONE_SECOND_TO_MIDNIGHT_BIF_ID: defaultdict(
                None,
                {
                    DEFAULT_COORDINATE: overpayment_balance_ts,
                },
            )
        }

        mock_deep_copy_balances.return_value = BalanceDefaultDict(
            mapping={
                DEFAULT_COORDINATE: SentinelBalance(""),
            }
        )

        mock_vault = self.create_mock(
            balances_interval_fetchers_mapping=balances_interval_fetchers_mapping,
            last_execution_datetimes={credit_card.EVENT_ACCRUE: effective_datetime},
        )

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={**self.common_get_param_return_values},
        )

        mock_get_supported_txn_types.return_value = {}
        mock_get_supported_fee_types.return_value = {}

        mock_is_revolver.return_value = True

        def accrue_interest_side_effect(
            vault,
            accrual_cut_off_dt,
            denomination,
            balances,
            instructions,
            supported_txn_types,
            supported_fee_types,
            txn_types_to_charge_interest_from_txn_date,
            txn_types_in_interest_free_period,
            is_revolver,
        ):
            instructions.extend(accrual_instructions)
            return sentinel.interest_accruals_by_sub_type

        mock_accrue_interest.side_effect = accrue_interest_side_effect

        def charge_interest_side_effect(
            vault,
            is_revolver,
            denomination,
            accruals_by_sub_type,
            txn_types_to_charge_interest_from_txn_date,
            in_flight_balances,
            instructions,
            txn_types_in_interest_free_period,
        ):
            instructions.extend(charge_interest_instructions)

        mock_charge_interest.side_effect = charge_interest_side_effect

        mock_adjust_aggregate_balances.return_value = adjust_aggregate_balances_instructions

        txn_types_to_charge_interest_from_txn_date: list = []
        txn_types_in_interest_free_period = {
            "cash_advance": [],
            "purchase": [],
            "balance_transfer": ["REF1"],
        }

        # construct expected result
        expected_result = [
            PostingInstructionsDirective(
                posting_instructions=[
                    *accrual_instructions,
                    *charge_interest_instructions,
                    *adjust_aggregate_balances_instructions,
                ],
                client_batch_id="ACCRUE_INTEREST-MOCK_HOOK",
                value_datetime=accrual_cut_off_dt,
            )
        ]

        # run hook
        result = credit_card._process_interest_accrual_and_charging(
            vault=mock_vault, effective_datetime=effective_datetime
        )

        # validate result
        self.assertEqual(result, expected_result)

        mock_is_flag_in_list_applied.assert_called_once_with(
            vault=mock_vault,
            parameter_name="accrual_blocking_flags",
            effective_datetime=effective_datetime,
        )

        mock_accrue_interest.assert_called_once_with(
            mock_vault,
            accrual_cut_off_dt,
            "GBP",
            mock_deep_copy_balances.return_value,
            ANY,
            mock_get_supported_txn_types.return_value,
            mock_get_supported_fee_types.return_value,
            txn_types_to_charge_interest_from_txn_date,
            txn_types_in_interest_free_period,
            mock_is_revolver.return_value,
        )

        mock_charge_interest.assert_called_once_with(
            mock_vault,
            mock_is_revolver.return_value,
            "GBP",
            sentinel.interest_accruals_by_sub_type,
            txn_types_to_charge_interest_from_txn_date,
            mock_deep_copy_balances.return_value,
            ANY,
            txn_types_in_interest_free_period,
        )

        mock_adjust_aggregate_balances.assert_called_once_with(
            mock_vault,
            "GBP",
            mock_deep_copy_balances.return_value,
            effective_datetime,
            available=False,
            outstanding=False,
            full_outstanding=True,
        )

    @patch.object(credit_card.utils, "is_flag_in_list_applied")
    def test_process_interest_accrual_and_charging_with_accrual_blocking_flag(
        self,
        mock_is_flag_in_list_applied: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock()
        mock_is_flag_in_list_applied.return_value = True

        # construct expected result
        expected_result: list = []

        # run hook
        result = credit_card._process_interest_accrual_and_charging(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME
        )

        # validate result
        self.assertEqual(result, expected_result)

    @patch.object(credit_card.utils, "is_flag_in_list_applied")
    @patch.object(credit_card, "_deep_copy_balances")
    @patch.object(credit_card.utils, "get_parameter")
    @patch.object(credit_card, "_get_supported_txn_types")
    @patch.object(credit_card, "_get_supported_fee_types")
    @patch.object(credit_card, "_is_revolver")
    @patch.object(credit_card, "_accrue_interest")
    @patch.object(credit_card, "_charge_interest")
    @patch.object(credit_card, "_adjust_aggregate_balances")
    def test_process_interest_accrual_and_charging_with_no_directives_returned(
        self,
        mock_adjust_aggregate_balances: MagicMock,
        mock_charge_interest: MagicMock,
        mock_accrue_interest: MagicMock,
        mock_is_revolver: MagicMock,
        mock_get_supported_fee_types: MagicMock,
        mock_get_supported_txn_types: MagicMock,
        mock_get_parameter: MagicMock,
        mock_deep_copy_balances: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock()
        mock_is_flag_in_list_applied.return_value = False

        accrual_instructions: list = []
        charge_interest_instructions: list = []
        adjust_aggregate_balances_instructions: list = []

        start_of_period = datetime(2020, 1, 2, 3, 4, 5, 6, tzinfo=ZoneInfo("UTC"))
        effective_datetime = datetime(2020, 4, 5, 6, 7, 8, 9, tzinfo=ZoneInfo("UTC"))
        accrual_cut_off_dt = effective_datetime.replace(hour=0, minute=0, second=0) - relativedelta(
            microseconds=1
        )

        overpayment_balance_ts = BalanceTimeseries(
            [
                (start_of_period, SentinelBalance("start_of_period_overpayment")),
                (effective_datetime, SentinelBalance("effective_datetime_overpayment")),
            ]
        )
        balances_interval_fetchers_mapping = {
            credit_card.ONE_SECOND_TO_MIDNIGHT_BIF_ID: defaultdict(
                None,
                {
                    DEFAULT_COORDINATE: overpayment_balance_ts,
                },
            )
        }

        mock_deep_copy_balances.return_value = BalanceDefaultDict(
            mapping={
                DEFAULT_COORDINATE: SentinelBalance(""),
            }
        )

        mock_vault = self.create_mock(
            balances_interval_fetchers_mapping=balances_interval_fetchers_mapping,
            last_execution_datetimes={credit_card.EVENT_ACCRUE: effective_datetime},
        )

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={**self.common_get_param_return_values},
        )

        mock_get_supported_txn_types.return_value = {}
        mock_get_supported_fee_types.return_value = {}

        mock_is_revolver.return_value = True

        def accrue_interest_side_effect(
            vault,
            accrual_cut_off_dt,
            denomination,
            balances,
            instructions,
            supported_txn_types,
            supported_fee_types,
            txn_types_to_charge_interest_from_txn_date,
            txn_types_in_interest_free_period,
            is_revolver,
        ):
            instructions.extend(accrual_instructions)
            return sentinel.interest_accruals_by_sub_type

        mock_accrue_interest.side_effect = accrue_interest_side_effect

        def charge_interest_side_effect(
            vault,
            is_revolver,
            denomination,
            accruals_by_sub_type,
            txn_types_to_charge_interest_from_txn_date,
            in_flight_balances,
            instructions,
            txn_types_in_interest_free_period,
        ):
            instructions.extend(charge_interest_instructions)

        mock_charge_interest.side_effect = charge_interest_side_effect

        mock_adjust_aggregate_balances.return_value = adjust_aggregate_balances_instructions

        txn_types_to_charge_interest_from_txn_date: list = []
        txn_types_in_interest_free_period = {
            "cash_advance": [],
            "purchase": [],
            "balance_transfer": ["REF1"],
        }

        # construct expected result
        expected_result: list = []

        # run hook
        result = credit_card._process_interest_accrual_and_charging(
            vault=mock_vault, effective_datetime=effective_datetime
        )

        # validate result
        self.assertEqual(result, expected_result)

        mock_is_flag_in_list_applied.assert_called_once_with(
            vault=mock_vault,
            parameter_name="accrual_blocking_flags",
            effective_datetime=effective_datetime,
        )

        mock_accrue_interest.assert_called_once_with(
            mock_vault,
            accrual_cut_off_dt,
            "GBP",
            mock_deep_copy_balances.return_value,
            ANY,
            mock_get_supported_txn_types.return_value,
            mock_get_supported_fee_types.return_value,
            txn_types_to_charge_interest_from_txn_date,
            txn_types_in_interest_free_period,
            mock_is_revolver.return_value,
        )

        mock_charge_interest.assert_called_once_with(
            mock_vault,
            mock_is_revolver.return_value,
            "GBP",
            sentinel.interest_accruals_by_sub_type,
            txn_types_to_charge_interest_from_txn_date,
            mock_deep_copy_balances.return_value,
            ANY,
            txn_types_in_interest_free_period,
        )

        mock_adjust_aggregate_balances.assert_called_once_with(
            mock_vault,
            "GBP",
            mock_deep_copy_balances.return_value,
            effective_datetime,
            available=False,
            outstanding=False,
            full_outstanding=True,
        )


@patch.object(credit_card, "_process_statement_cut_off")
class StatementCutoffScheduledEventTest(CreditCardTestBase):
    def test_SCOD_scheduled_event(
        self,
        mock_process_statement_cut_off: MagicMock,
    ):
        # construct mocks
        scod_notification = SentinelAccountNotificationDirective("scod")
        scod_posting_instruction_directive = SentinelPostingInstructionsDirective("scod")
        mock_process_statement_cut_off.return_value = (
            [scod_notification],
            [scod_posting_instruction_directive],
        )
        mock_vault = self.create_mock()

        # construct expected result
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[scod_posting_instruction_directive],
            account_notification_directives=[scod_notification],
        )

        # run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=credit_card.EVENT_SCOD
        )
        result = credit_card.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)

        # assert
        self.assertEqual(result, expected_result)
        mock_process_statement_cut_off.assert_called_once_with(mock_vault, DEFAULT_DATETIME)
