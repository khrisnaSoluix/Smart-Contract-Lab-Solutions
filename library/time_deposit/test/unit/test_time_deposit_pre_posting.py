# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel

# library
import library.time_deposit.contracts.template.time_deposit as time_deposit
from library.time_deposit.test.unit.test_time_deposit_common import TimeDepositTest

# features
import library.features.common.fetchers as fetchers
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import PrePostingHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PrePostingHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelRejection,
)


class PrePostingHookCommonTest(TimeDepositTest):
    def setUp(self) -> None:
        self.mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("balances_observation")
            },
        )

        self.expected_rejection = SentinelRejection("rejection")

        self.posting_instructions = [self.inbound_hard_settlement(amount=Decimal("1"))]
        self.hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=self.posting_instructions,
            client_transactions=sentinel.client_transactions,
        )

        self.expected_result = PrePostingHookResult(rejection=self.expected_rejection)

        patch_get_parameter = patch.object(time_deposit.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": self.default_denom}
        )

        patch_validate_single_hard_settlement_or_transfer = patch.object(
            time_deposit.utils, "validate_single_hard_settlement_or_transfer"
        )
        self.mock_validate_single_hard_settlement_or_transfer = (
            patch_validate_single_hard_settlement_or_transfer.start()
        )
        self.mock_validate_single_hard_settlement_or_transfer.return_value = None

        patch_is_force_override = patch.object(time_deposit.utils, "is_force_override")
        self.mock_is_force_override = patch_is_force_override.start()
        self.mock_is_force_override.return_value = None

        patch_validate_denomination = patch.object(time_deposit.utils, "validate_denomination")
        self.mock_validate_denomination = patch_validate_denomination.start()
        self.mock_validate_denomination.return_value = None

        patch_validate_maximum_balance_limit = patch.object(
            time_deposit.maximum_balance_limit, "validate"
        )
        self.mock_validate_maximum_balance_limit = patch_validate_maximum_balance_limit.start()
        self.mock_validate_maximum_balance_limit.return_value = None

        patch_get_grace_period_parameter = patch.object(
            time_deposit.grace_period, "get_grace_period_parameter"
        )
        self.mock_get_grace_period_parameter = patch_get_grace_period_parameter.start()
        self.mock_get_grace_period_parameter.return_value = 0

        patch_validate_postings_deposit_maturity = patch.object(
            time_deposit.deposit_maturity, "validate_postings"
        )
        self.mock_validate_postings_deposit_maturity = (
            patch_validate_postings_deposit_maturity.start()
        )
        self.mock_validate_postings_deposit_maturity.return_value = None

        patch_validate_withdrawal_fees = patch.object(time_deposit.withdrawal_fees, "validate")
        self.mock_validate_withdrawal_fees = patch_validate_withdrawal_fees.start()
        self.mock_validate_withdrawal_fees.return_value = None

        patch_validate_withdrawals_with_number_of_interest_days_fee = patch.object(
            time_deposit, "_validate_withdrawals_with_number_of_interest_days_fee"
        )
        self.mock_validate_withdrawal_fees_interest_days_fee = (
            patch_validate_withdrawals_with_number_of_interest_days_fee.start()
        )
        self.mock_validate_withdrawal_fees_interest_days_fee.return_value = None

        self.addCleanup(patch.stopall)
        return super().setUp()


class NewTimeDepositPrePostingHookTest(PrePostingHookCommonTest):
    def setUp(self) -> None:
        patch_validate_minimum_initial_deposit = patch.object(
            time_deposit.minimum_initial_deposit, "validate"
        )
        self.mock_validate_minimum_initial_deposit = patch_validate_minimum_initial_deposit.start()
        self.mock_validate_minimum_initial_deposit.return_value = None

        patch_validate_deposit_period = patch.object(time_deposit.deposit_period, "validate")
        self.mock_validate_deposit_period = patch_validate_deposit_period.start()
        self.mock_validate_deposit_period.return_value = None

        return super().setUp()

    def test_postings_are_accepted_when_force_override_is_active(self):
        self.mock_is_force_override.return_value = True

        hook_result = time_deposit.pre_posting_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        self.assertIsNone(hook_result)
        self.mock_is_force_override.assert_called_once_with(
            posting_instructions=self.posting_instructions
        )

    def test_rejects_postings_when_denomination_is_not_supported(self):
        self.mock_validate_denomination.return_value = self.expected_rejection

        hook_result = time_deposit.pre_posting_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        self.assertEqual(self.expected_result, hook_result)
        self.mock_get_parameter.assert_has_calls(
            [
                call(vault=self.mock_vault, name="denomination", at_datetime=None),
            ]
        )
        self.mock_validate_denomination.assert_called_once_with(
            posting_instructions=self.posting_instructions,
            accepted_denominations=["GBP"],
        )

    def test_accept_postings_when_denomination_is_supported(self):
        hook_result = time_deposit.pre_posting_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        self.assertIsNone(hook_result)
        self.mock_get_parameter.assert_has_calls(
            [
                call(vault=self.mock_vault, name="denomination", at_datetime=None),
            ]
        )
        self.mock_validate_denomination.assert_called_once_with(
            posting_instructions=self.posting_instructions,
            accepted_denominations=["GBP"],
        )

    def test_rejects_postings_when_maximum_balance_is_surpassed(self):
        self.mock_validate_maximum_balance_limit.return_value = self.expected_rejection

        hook_result = time_deposit.pre_posting_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        self.assertEqual(self.expected_result, hook_result)
        self.mock_validate_maximum_balance_limit.assert_called_once_with(
            vault=self.mock_vault,
            postings=self.posting_instructions,
            denomination=self.default_denom,
            balances=sentinel.balances_balances_observation,
        )

    def test_accept_posting_when_deposit_validation_passes(self):
        hook_result = time_deposit.pre_posting_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        self.assertEqual(hook_result, None)
        self.mock_get_parameter.assert_has_calls(
            [
                call(vault=self.mock_vault, name="denomination", at_datetime=None),
            ]
        )
        self.mock_validate_deposit_period.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=self.posting_instructions,
            denomination=self.default_denom,
            balances=sentinel.balances_balances_observation,
        )

    def test_reject_posting_when_deposit_validation_fails(self):
        self.mock_validate_deposit_period.return_value = self.expected_rejection

        hook_result = time_deposit.pre_posting_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        self.assertEqual(self.expected_result, hook_result)
        self.mock_get_parameter.assert_has_calls(
            [
                call(vault=self.mock_vault, name="denomination", at_datetime=None),
            ]
        )
        self.mock_validate_deposit_period.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=self.posting_instructions,
            denomination=self.default_denom,
            balances=sentinel.balances_balances_observation,
        )

    def test_reject_posting_when_posting_type_is_invalid(self):
        self.mock_validate_single_hard_settlement_or_transfer.return_value = self.expected_rejection

        hook_result = time_deposit.pre_posting_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        self.assertEqual(self.expected_result, hook_result)
        self.mock_validate_single_hard_settlement_or_transfer.assert_called_once_with(
            posting_instructions=self.posting_instructions
        )

    def test_reject_posting_when_initial_deposit_less_than_minimum_initial_deposit(self):
        self.mock_validate_minimum_initial_deposit.return_value = self.expected_rejection

        hook_result = time_deposit.pre_posting_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        # assertions
        self.assertEqual(self.expected_result, hook_result)
        self.mock_validate_minimum_initial_deposit.assert_called_once_with(
            vault=self.mock_vault,
            postings=self.posting_instructions,
            denomination=self.default_denom,
            balances=sentinel.balances_balances_observation,
        )

    def test_postings_are_rejected_upon_account_maturity(self):
        self.mock_validate_postings_deposit_maturity.return_value = self.expected_rejection

        hook_result = time_deposit.pre_posting_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        self.assertEqual(self.expected_result, hook_result)
        self.mock_validate_postings_deposit_maturity.assert_called_once_with(
            vault=self.mock_vault, effective_datetime=DEFAULT_DATETIME
        )

    def test_postings_are_rejected_if_does_not_meet_fee_charging_conditions(self):
        self.mock_validate_withdrawal_fees.return_value = self.expected_rejection

        hook_result = time_deposit.pre_posting_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        self.assertEqual(self.expected_result, hook_result)
        self.mock_validate_withdrawal_fees.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=self.posting_instructions,
            denomination=self.default_denom,
            balances=sentinel.balances_balances_observation,
            balance_adjustments=time_deposit.TIME_DEPOSIT_DEFAULT_BALANCE_ADJUSTMENTS,
        )

    def test_postings_are_rejected_if_does_not_meet_fee_charging_conditions_with_interest_days_fee(
        self,
    ):
        self.mock_validate_withdrawal_fees_interest_days_fee.return_value = self.expected_rejection

        hook_result = time_deposit.pre_posting_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        self.assertEqual(self.expected_result, hook_result)
        self.mock_validate_withdrawal_fees_interest_days_fee.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=self.posting_instructions,
            denomination=self.default_denom,
            balances=sentinel.balances_balances_observation,
            balance_adjustments=time_deposit.TIME_DEPOSIT_DEFAULT_BALANCE_ADJUSTMENTS,
        )


class RenewedTimeDepositPrePostingHookTest(PrePostingHookCommonTest):
    def setUp(self) -> None:
        return super().setUp()

    @patch.object(time_deposit.grace_period, "validate_deposit")
    def test_postings_accepted_if_grace_period_validate_returns_none(
        self, mock_grace_period_validate: MagicMock
    ):
        self.mock_get_grace_period_parameter.return_value = 1
        mock_grace_period_validate.return_value = None

        hook_result = time_deposit.pre_posting_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        self.assertIsNone(hook_result)
        mock_grace_period_validate.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=self.posting_instructions,
            denomination=self.default_denom,
        )

    @patch.object(time_deposit.grace_period, "validate_deposit")
    def test_deposit_postings_rejected_if_grace_period_validate_returns_rejection(
        self, mock_grace_period_validate: MagicMock
    ):
        self.mock_get_grace_period_parameter.return_value = 1
        sentinel_rejection = SentinelRejection("grace_period_rejection")
        mock_grace_period_validate.return_value = sentinel_rejection

        expected_result = PrePostingHookResult(rejection=sentinel_rejection)
        hook_result = time_deposit.pre_posting_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        self.assertEqual(hook_result, expected_result)
        mock_grace_period_validate.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=self.posting_instructions,
            denomination=self.default_denom,
        )
