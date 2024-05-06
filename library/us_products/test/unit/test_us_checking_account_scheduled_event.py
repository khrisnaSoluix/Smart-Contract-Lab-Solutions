# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
from library.us_products.contracts.template import us_checking_account
from library.us_products.test.parameters import TEST_DENOMINATION
from library.us_products.test.unit.test_us_checking_account_common import CheckingAccountTest

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import ScheduledEventHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DATETIME,
    construct_parameter_timeseries,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PostingInstructionsDirective,
    ScheduledEventHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelCustomInstruction,
    SentinelUpdateAccountEventTypeDirective,
)


@patch.object(us_checking_account.dormancy, "is_account_dormant")
class DummyEventTest(CheckingAccountTest):
    def test_schedule_with_dummy_event_type(
        self,
        mock_is_account_dormant: MagicMock,
    ):
        mock_is_account_dormant.return_value = False
        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type="DUMMY"
        )
        result = us_checking_account.scheduled_event_hook(
            vault=sentinel.vault, hook_arguments=hook_arguments
        )
        self.assertIsNone(result)


@patch.object(us_checking_account.tiered_interest_accrual, "accrue_interest")
@patch.object(us_checking_account.dormancy, "is_account_dormant")
class InterestAccrualTest(CheckingAccountTest):
    def test_interest_accrued(
        self,
        mock_is_account_dormant: MagicMock,
        mock_accrue_interest: MagicMock,
    ):
        # construct values
        mock_vault = self.create_mock()
        mock_is_account_dormant.return_value = False
        mock_accrue_interest.return_value = [SentinelCustomInstruction("accrue_interest")]
        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=us_checking_account.tiered_interest_accrual.ACCRUAL_EVENT,
        )

        # expected result
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[SentinelCustomInstruction("accrue_interest")],
                    value_datetime=DEFAULT_DATETIME,
                    client_batch_id=(
                        f"MOCK_HOOK_{us_checking_account.tiered_interest_accrual.ACCRUAL_EVENT}"
                    ),
                )
            ]
        )

        # run hook
        result = us_checking_account.scheduled_event_hook(mock_vault, hook_arguments)
        self.assertEquals(result, expected_result)

        # call assertions
        mock_accrue_interest.assert_called_once_with(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME
        )

    def test_hook_returns_none_with_no_accrual_instructions(
        self,
        mock_is_account_dormant: MagicMock,
        mock_accrue_interest: MagicMock,
    ):
        # construct values
        mock_vault = self.create_mock()
        mock_is_account_dormant.return_value = False
        mock_accrue_interest.return_value = []
        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=us_checking_account.tiered_interest_accrual.ACCRUAL_EVENT,
        )

        # run hook
        result = us_checking_account.scheduled_event_hook(mock_vault, hook_arguments)
        self.assertIsNone(result)

        # call assertions
        mock_accrue_interest.assert_called_once_with(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME
        )


@patch.object(us_checking_account.interest_application, "update_next_schedule_execution")
@patch.object(us_checking_account.interest_application, "apply_interest")
@patch.object(us_checking_account.dormancy, "is_account_dormant")
class InterestApplicationTest(CheckingAccountTest):
    def test_interest_applied(
        self,
        mock_is_account_dormant: MagicMock,
        mock_apply_interest: MagicMock,
        mock_update_next_schedule_execution: MagicMock,
    ):
        # construct values
        mock_vault = self.create_mock()
        mock_is_account_dormant.return_value = False
        mock_apply_interest.return_value = [SentinelCustomInstruction("apply_interest")]
        mock_update_next_schedule_execution.return_value = SentinelUpdateAccountEventTypeDirective(
            "next_schedule"
        )
        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=us_checking_account.interest_application.APPLICATION_EVENT,
        )

        # expected result
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[SentinelCustomInstruction("apply_interest")],
                    value_datetime=DEFAULT_DATETIME,
                    client_batch_id=(
                        f"MOCK_HOOK_{us_checking_account.interest_application.APPLICATION_EVENT}"
                    ),
                )
            ],
            update_account_event_type_directives=[
                SentinelUpdateAccountEventTypeDirective("next_schedule")
            ],
        )

        # run hook
        result = us_checking_account.scheduled_event_hook(mock_vault, hook_arguments)
        self.assertEquals(result, expected_result)

        # call assertions
        mock_apply_interest.assert_called_once_with(
            vault=mock_vault, account_type=us_checking_account.PRODUCT_NAME
        )
        mock_update_next_schedule_execution.assert_called_once_with(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME
        )

    def test_hook_with_no_application_instructions(
        self,
        mock_is_account_dormant: MagicMock,
        mock_apply_interest: MagicMock,
        mock_update_next_schedule_execution: MagicMock,
    ):
        # construct values
        mock_vault = self.create_mock()
        mock_is_account_dormant.return_value = False
        mock_apply_interest.return_value = []
        mock_update_next_schedule_execution.return_value = SentinelUpdateAccountEventTypeDirective(
            "next_schedule"
        )
        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=us_checking_account.interest_application.APPLICATION_EVENT,
        )

        # expected result
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[],
            update_account_event_type_directives=[
                SentinelUpdateAccountEventTypeDirective("next_schedule")
            ],
        )

        # run hook
        result = us_checking_account.scheduled_event_hook(mock_vault, hook_arguments)
        self.assertEqual(expected_result, result)

        # call assertions
        mock_apply_interest.assert_called_once_with(
            vault=mock_vault, account_type=us_checking_account.PRODUCT_NAME
        )
        mock_update_next_schedule_execution.assert_called_once_with(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME
        )


@patch.object(us_checking_account.inactivity_fee, "apply")
@patch.object(us_checking_account.utils, "is_flag_in_list_applied")
@patch.object(us_checking_account.dormancy, "is_account_dormant")
class ScheduledEventInactivityFeeTest(CheckingAccountTest):
    def test_inactivity_fee_account_not_dormant_and_not_inactive(
        self,
        mock_is_account_dormant: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_inactivity_fee_apply: MagicMock,
    ):
        # mocks
        mock_is_account_dormant.return_value = False
        mock_is_flag_in_list_applied.return_value = False

        # hook call
        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=us_checking_account.inactivity_fee.APPLICATION_EVENT,
        )
        hook_result = us_checking_account.scheduled_event_hook(sentinel.vault, hook_arguments)

        # assertions
        self.assertIsNone(hook_result)
        mock_inactivity_fee_apply.assert_not_called()

    def test_inactivity_fee_account_not_dormant_and_inactive(
        self,
        mock_is_account_dormant: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_inactivity_fee_apply: MagicMock,
    ):
        # mocks
        mock_is_account_dormant.return_value = False
        mock_is_flag_in_list_applied.return_value = True
        mock_inactivity_fee_apply.return_value = [SentinelCustomInstruction("inactivity_fee")]
        mock_vault = self.create_mock()

        # expected result
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[SentinelCustomInstruction("inactivity_fee")],
                    value_datetime=DEFAULT_DATETIME,
                    client_batch_id="MOCK_HOOK_"
                    f"{us_checking_account.inactivity_fee.APPLICATION_EVENT}",
                )
            ]
        )

        # hook call
        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=us_checking_account.inactivity_fee.APPLICATION_EVENT,
        )
        hook_result = us_checking_account.scheduled_event_hook(mock_vault, hook_arguments)

        # assertions
        self.assertEquals(hook_result, expected_result)
        mock_inactivity_fee_apply.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            available_balance_feature=us_checking_account.overdraft_coverage.OverdraftCoverageAvailableBalance,  # noqa: E501
        )

    def test_inactivity_fee_account_dormant_and_inactive(
        self,
        mock_is_account_dormant: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_inactivity_fee_apply: MagicMock,
    ):
        # mocks
        mock_is_account_dormant.return_value = True
        mock_is_flag_in_list_applied.return_value = True

        # hook call
        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=us_checking_account.inactivity_fee.APPLICATION_EVENT,
        )
        hook_result = us_checking_account.scheduled_event_hook(sentinel.vault, hook_arguments)

        # assertions
        self.assertIsNone(hook_result)
        mock_inactivity_fee_apply.assert_not_called()


@patch.object(us_checking_account.minimum_monthly_balance, "apply_minimum_balance_fee")
@patch.object(us_checking_account.dormancy, "is_account_dormant")
class ApplyMinimumBalanceFeeTest(CheckingAccountTest):
    def test_monthly_minimum_balance_fee_applied(
        self,
        mock_is_account_dormant: MagicMock,
        mock_apply_minimum_balance_fee: MagicMock,
    ):
        # construct values
        event_type = us_checking_account.minimum_monthly_balance.APPLY_MINIMUM_MONTHLY_BALANCE_EVENT
        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=event_type,
        )

        # construct mocks
        mock_vault = self.create_mock(
            parameter_ts=construct_parameter_timeseries(
                parameter_name_to_value_map={
                    us_checking_account.PARAM_DENOMINATION: TEST_DENOMINATION
                },
                default_datetime=DEFAULT_DATETIME,
            )
        )
        mock_is_account_dormant.return_value = False
        mock_apply_minimum_balance_fee.return_value = [
            SentinelCustomInstruction("apply_minimum_balance_fee")
        ]

        # expected result
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[SentinelCustomInstruction("apply_minimum_balance_fee")],
                    value_datetime=DEFAULT_DATETIME,
                    client_batch_id=f"MOCK_HOOK_{event_type}",
                )
            ]
        )

        # run hook
        result = us_checking_account.scheduled_event_hook(mock_vault, hook_arguments)
        self.assertEquals(result, expected_result)

        # call assertions
        mock_apply_minimum_balance_fee.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination="USD",
            available_balance_feature=us_checking_account.overdraft_coverage.OverdraftCoverageAvailableBalance,  # noqa: E501
        )

    def test_hook_returns_none_with_no_instructions(
        self,
        mock_is_account_dormant: MagicMock,
        mock_apply_minimum_balance_fee: MagicMock,
    ):
        # construct values
        mock_vault = self.create_mock(
            parameter_ts=construct_parameter_timeseries(
                parameter_name_to_value_map={
                    us_checking_account.PARAM_DENOMINATION: TEST_DENOMINATION
                },
                default_datetime=DEFAULT_DATETIME,
            )
        )
        mock_is_account_dormant.return_value = False
        mock_apply_minimum_balance_fee.return_value = []
        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=(
                us_checking_account.minimum_monthly_balance.APPLY_MINIMUM_MONTHLY_BALANCE_EVENT
            ),
        )

        # run hook
        result = us_checking_account.scheduled_event_hook(mock_vault, hook_arguments)
        self.assertIsNone(result)

        # call assertions
        mock_apply_minimum_balance_fee.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination="USD",
            available_balance_feature=us_checking_account.overdraft_coverage.OverdraftCoverageAvailableBalance,  # noqa: E501
        )

    def test_monthly_minimum_balance_fee_not_applied_when_dormant(
        self,
        mock_is_account_dormant: MagicMock,
        mock_apply_minimum_balance_fee: MagicMock,
    ):
        # construct values
        mock_is_account_dormant.return_value = True
        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=(
                us_checking_account.minimum_monthly_balance.APPLY_MINIMUM_MONTHLY_BALANCE_EVENT
            ),
        )

        # run hook
        result = us_checking_account.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertIsNone(result)

        # call assertions
        mock_is_account_dormant.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
        )
        mock_apply_minimum_balance_fee.assert_not_called()


@patch.object(us_checking_account.direct_deposit_tracker, "reset_tracking_instructions")
@patch.object(us_checking_account.maintenance_fees, "apply_monthly_fee")
@patch.object(us_checking_account.dormancy, "is_account_dormant")
class MonthlyMaintenanceFeeTest(CheckingAccountTest):
    def test_monthly_maintenance_fee_applied(
        self,
        mock_is_account_dormant: MagicMock,
        mock_apply_monthly_fee: MagicMock,
        mock_reset_tracking_instructions: MagicMock,
    ):
        # construct values
        mock_vault = self.create_mock()
        mock_is_account_dormant.return_value = False
        mock_apply_monthly_fee.return_value = [SentinelCustomInstruction("monthly_fee")]
        mock_reset_tracking_instructions.return_value = [
            SentinelCustomInstruction("reset_tracking_instructions")
        ]
        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=us_checking_account.maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
        )

        # expected result
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[
                        SentinelCustomInstruction("monthly_fee"),
                        SentinelCustomInstruction("reset_tracking_instructions"),
                    ],
                    value_datetime=DEFAULT_DATETIME,
                    client_batch_id=(
                        f"MOCK_HOOK_{us_checking_account.maintenance_fees.APPLY_MONTHLY_FEE_EVENT}"
                    ),
                )
            ],
            update_account_event_type_directives=[],
        )

        # run hook
        result = us_checking_account.scheduled_event_hook(mock_vault, hook_arguments)
        self.assertEqual(expected_result, result)

        # call assertions
        mock_is_account_dormant.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
        )
        mock_apply_monthly_fee.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            monthly_fee_waive_conditions=[
                us_checking_account.minimum_monthly_balance.WAIVE_FEE_WITH_MEAN_BALANCE_ABOVE_THRESHOLD,  # noqa: E501
                us_checking_account.direct_deposit_tracker.WAIVE_FEE_AFTER_SUFFICIENT_DEPOSITS,
            ],
            available_balance_feature=us_checking_account.overdraft_coverage.OverdraftCoverageAvailableBalance,  # noqa: E501
        )
        mock_reset_tracking_instructions.assert_called_once_with(vault=mock_vault)

    def test_monthly_maintenance_fee_not_applied_when_dormant(
        self,
        mock_is_account_dormant: MagicMock,
        mock_apply_monthly_fee: MagicMock,
        mock_reset_tracking_instructions: MagicMock,
    ):
        # construct values
        mock_is_account_dormant.return_value = True
        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=us_checking_account.maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
        )

        # run hook
        result = us_checking_account.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertIsNone(result)

        # call assertions
        mock_is_account_dormant.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
        )
        mock_apply_monthly_fee.assert_not_called()
        mock_reset_tracking_instructions.assert_not_called()


@patch.object(us_checking_account.utils, "get_parameter")
@patch.object(us_checking_account.paper_statement_fee, "apply")
@patch.object(us_checking_account.dormancy, "is_account_dormant")
class PaperStatementFeeTest(CheckingAccountTest):
    def test_paper_statement_fee_applied(
        self,
        mock_is_account_dormant: MagicMock,
        mock_apply_paper_statement_fee: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # construct values
        event_type = us_checking_account.paper_statement_fee.APPLICATION_EVENT
        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=event_type,
        )

        # construct mocks
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={us_checking_account.PARAM_DENOMINATION: TEST_DENOMINATION}
        )
        mock_is_account_dormant.return_value = False
        mock_apply_paper_statement_fee.return_value = [
            SentinelCustomInstruction("apply_paper_statement_fee")
        ]

        # expected result
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[SentinelCustomInstruction("apply_paper_statement_fee")],
                    value_datetime=DEFAULT_DATETIME,
                    client_batch_id=f"MOCK_HOOK_{event_type}",
                )
            ]
        )

        # run hook
        result = us_checking_account.scheduled_event_hook(mock_vault, hook_arguments)
        self.assertEquals(result, expected_result)

        # call assertions
        mock_apply_paper_statement_fee.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            available_balance_feature=us_checking_account.overdraft_coverage.OverdraftCoverageAvailableBalance,  # noqa: E501
        )

    def test_paper_statement_fee_not_applied_when_dormant(
        self,
        mock_is_account_dormant: MagicMock,
        mock_paper_statement_fee_apply: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # mocks
        mock_is_account_dormant.return_value = True

        # hook call
        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=us_checking_account.paper_statement_fee.APPLICATION_EVENT,
        )
        hook_result = us_checking_account.scheduled_event_hook(sentinel.vault, hook_arguments)

        # assertions
        self.assertIsNone(hook_result)
        mock_paper_statement_fee_apply.assert_not_called()
