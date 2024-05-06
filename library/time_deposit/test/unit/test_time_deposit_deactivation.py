# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import patch, sentinel

# library
import library.time_deposit.contracts.template.time_deposit as time_deposit
from library.time_deposit.test.unit.test_time_deposit_common import TimeDepositTest

# features
import library.features.common.fetchers as fetchers
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import DeactivationHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DeactivationHookResult,
    PostingInstructionsDirective,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelCustomInstruction,
)


class DeactivationHookTest(TimeDepositTest):
    def setUp(self) -> None:
        self.mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live_balances"),
            },
        )

        self.hook_arguments = DeactivationHookArguments(
            effective_datetime=DEFAULT_DATETIME,
        )

        patch_get_parameter = patch.object(time_deposit.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={time_deposit.common_parameters.PARAM_DENOMINATION: self.default_denom}
        )

        patch_get_interest_reversal_postings = patch.object(
            time_deposit.fixed_interest_accrual, "get_interest_reversal_postings"
        )
        self.mock_get_interest_reversal_postings = patch_get_interest_reversal_postings.start()
        self.mock_get_interest_reversal_postings.return_value = [
            SentinelCustomInstruction("reverse_all_accrued_interest")
        ]

        patch_reset_applied_interest_tracker = patch.object(
            time_deposit, "_reset_applied_interest_tracker"
        )
        self.mock_reset_applied_interest_tracker = patch_reset_applied_interest_tracker.start()
        self.mock_reset_applied_interest_tracker.return_value = [
            SentinelCustomInstruction("reset_applied_interest")
        ]

        patch_reset_withdrawals_tracker = patch.object(
            time_deposit.withdrawal_fees, "reset_withdrawals_tracker"
        )
        self.mock_reset_withdrawals_tracker = patch_reset_withdrawals_tracker.start()
        self.mock_reset_withdrawals_tracker.return_value = [
            SentinelCustomInstruction("reset_withdrawals")
        ]

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_deactivation_hook_returns_cleanup_postings(self):
        expected_result = DeactivationHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[
                        *self.mock_get_interest_reversal_postings.return_value,
                        *self.mock_reset_applied_interest_tracker.return_value,
                        *self.mock_reset_withdrawals_tracker.return_value,
                    ],
                    value_datetime=DEFAULT_DATETIME,
                )
            ]
        )
        result = time_deposit.deactivation_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )
        self.assertEqual(result, expected_result)
        self.mock_reset_applied_interest_tracker.assert_called_once_with(
            balances=sentinel.balances_live_balances,
            account_id=self.mock_vault.account_id,
            denomination=self.default_denom,
        )
        self.mock_get_interest_reversal_postings.assert_called_once_with(
            vault=self.mock_vault,
            event_name="ACCOUNT_CLOSURE",
            account_type="TIME_DEPOSIT",
            balances=sentinel.balances_live_balances,
        )

    def test_deactivation_hook_returns_none_if_no_cleanup_posting_instructions(self):
        self.mock_reset_applied_interest_tracker.return_value = []
        self.mock_get_interest_reversal_postings.return_value = []
        self.mock_reset_withdrawals_tracker.return_value = []

        hook_result = time_deposit.deactivation_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        self.assertIsNone(hook_result)
        self.mock_reset_applied_interest_tracker.assert_called_once_with(
            balances=sentinel.balances_live_balances,
            account_id=self.mock_vault.account_id,
            denomination=self.default_denom,
        )
        self.mock_get_interest_reversal_postings.assert_called_once_with(
            vault=self.mock_vault,
            event_name="ACCOUNT_CLOSURE",
            account_type="TIME_DEPOSIT",
            balances=sentinel.balances_live_balances,
        )
