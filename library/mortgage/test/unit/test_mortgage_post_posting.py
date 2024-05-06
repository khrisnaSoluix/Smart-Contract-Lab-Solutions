# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# library
import library.mortgage.contracts.template.mortgage as mortgage
from library.mortgage.test.unit.test_mortgage_common import MortgageTestBase

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import PostPostingHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DEFAULT_ASSET,
    AccountNotificationDirective,
    Phase,
    Posting,
    PostingInstructionsDirective,
    PostPostingHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelAccountNotificationDirective,
    SentinelBalancesObservation,
    SentinelCustomInstruction,
)


@patch.object(mortgage.utils, "is_force_override")
@patch.object(mortgage.utils, "get_parameter")
class PostPostingHookTest(MortgageTestBase):
    # define common return types to avoid duplicated definitions across tests
    common_get_param_return_values = {
        "denomination": "GBP",
    }

    def test_hook_force_override_returns_none(
        self,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        # construct mocks
        mock_is_force_override.return_value = True

        # run function
        hook_args = hook_args = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.posting_instructions,
            client_transactions=sentinel.client_transactions,
        )
        result = mortgage.post_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)
        self.assertIsNone(result)
        mock_get_parameter.assert_not_called()

    def test_balance_delta_zero_returns_none(
        self, mock_get_parameter: MagicMock, mock_is_force_override: MagicMock
    ):
        # construct mocks
        mock_vault = self.create_mock()
        mock_is_force_override.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={**self.common_get_param_return_values}
        )

        posting_instructions = [
            # posting_balance_delta is the net of the DEFAULT address
            # so will evaluate to 0 for this PI
            self.custom_instruction(
                postings=[
                    Posting(
                        credit=True,
                        amount=Decimal("10"),
                        denomination="GBP",
                        account_id=mock_vault.account_id,
                        account_address="DUMMY_ADDRESS_1",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    Posting(
                        credit=False,
                        amount=Decimal("10"),
                        denomination="GBP",
                        account_id=mock_vault.account_id,
                        account_address="DUMMY_ADDRESS_2",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                ]
            )
        ]

        # run function
        hook_args = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=posting_instructions,
            client_transactions=sentinel.client_transactions,
        )
        result = mortgage.post_posting_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertIsNone(result)

    @patch.object(mortgage, "_move_balance_custom_instructions")
    @patch.object(mortgage, "_is_interest_adjustment")
    def test_balance_delta_positive_returns_balance_movement_instructions_penalties(
        self,
        mock_is_interest_adjustment: MagicMock,
        mock_move_balance_custom_instructions: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        # expected values
        expected_cis = [SentinelCustomInstruction("move_balance")]

        # construct mocks
        mock_vault = self.create_mock()
        mock_is_force_override.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={**self.common_get_param_return_values}
        )
        mock_is_interest_adjustment.return_value = False
        mock_move_balance_custom_instructions.return_value = expected_cis

        posting_instructions = [
            self.outbound_hard_settlement(amount=Decimal("10"), instruction_details={"fee": "true"})
        ]
        # construct expected result
        expected_result = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_cis,  # type: ignore
                    value_datetime=DEFAULT_DATETIME,
                )
            ]
        )

        # run function
        hook_args = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=posting_instructions,
            client_transactions=sentinel.client_transactions,
        )
        result = mortgage.post_posting_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertEqual(expected_result, result)
        mock_move_balance_custom_instructions.assert_called_once_with(
            amount=Decimal("10"),
            denomination="GBP",
            vault_account=mock_vault.account_id,
            balance_address=mortgage.lending_addresses.PENALTIES,
        )

    @patch.object(mortgage, "_get_interest_adjustment_custom_instructions")
    @patch.object(mortgage, "_get_interest_to_revert")
    @patch.object(mortgage, "_move_balance_custom_instructions")
    @patch.object(mortgage, "_is_interest_adjustment")
    def test_balance_delta_positive_returns_balance_movement_instructions_interest_due_do_not_waive(
        self,
        mock_is_interest_adjustment: MagicMock,
        mock_move_balance_custom_instructions: MagicMock,
        mock_get_interest_to_revert: MagicMock,
        mock_get_interest_adjustment_custom_instructions: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        # expected values
        expected_cis = [SentinelCustomInstruction("move_balance")]

        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                mortgage.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
        )
        mock_is_force_override.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                **self.common_get_param_return_values,
                "interest_received_account": sentinel.interest_received_account,
            }
        )
        mock_is_interest_adjustment.return_value = True
        mock_move_balance_custom_instructions.return_value = expected_cis
        mock_get_interest_to_revert.return_value = Decimal("0")
        mock_get_interest_adjustment_custom_instructions.return_value = []

        posting_instructions = [
            self.outbound_hard_settlement(
                amount=Decimal("10"), instruction_details={"interest_adjustment": "true"}
            )
        ]
        # construct expected result
        expected_result = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_cis,  # type: ignore
                    value_datetime=DEFAULT_DATETIME,
                )
            ]
        )

        # run function
        hook_args = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=posting_instructions,
            client_transactions=sentinel.client_transactions,
        )
        result = mortgage.post_posting_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertEqual(expected_result, result)
        mock_move_balance_custom_instructions.assert_called_once_with(
            amount=Decimal("10"),
            denomination="GBP",
            vault_account=mock_vault.account_id,
            balance_address=mortgage.lending_addresses.INTEREST_DUE,
        )
        mock_get_interest_adjustment_custom_instructions.assert_called_once_with(
            amount=Decimal("0"),
            denomination="GBP",
            vault_account=mock_vault.account_id,
            interest_received_account=sentinel.interest_received_account,
        )

    @patch.object(mortgage, "_get_interest_adjustment_custom_instructions")
    @patch.object(mortgage, "_get_interest_to_revert")
    @patch.object(mortgage, "_move_balance_custom_instructions")
    @patch.object(mortgage, "_is_interest_adjustment")
    def test_balance_delta_positive_returns_balance_movement_instructions_interest_due_waive(
        self,
        mock_is_interest_adjustment: MagicMock,
        mock_move_balance_custom_instructions: MagicMock,
        mock_get_interest_to_revert: MagicMock,
        mock_get_interest_adjustment_custom_instructions: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        # expected values
        move_balance_cis = [SentinelCustomInstruction("move_balance")]
        interest_waiver_cis = [SentinelCustomInstruction("interest_waiver")]
        expected_cis = move_balance_cis + interest_waiver_cis

        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                mortgage.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
        )
        mock_is_force_override.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                **self.common_get_param_return_values,
                "interest_received_account": sentinel.interest_received_account,
            }
        )
        mock_is_interest_adjustment.return_value = True
        mock_move_balance_custom_instructions.return_value = move_balance_cis
        mock_get_interest_to_revert.return_value = Decimal("5")
        mock_get_interest_adjustment_custom_instructions.return_value = interest_waiver_cis

        posting_instructions = [
            self.outbound_hard_settlement(
                amount=Decimal("10"), instruction_details={"interest_adjustment": "true"}
            )
        ]
        # construct expected result
        expected_result = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_cis,  # type: ignore
                    value_datetime=DEFAULT_DATETIME,
                )
            ]
        )

        # run function
        hook_args = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=posting_instructions,
            client_transactions=sentinel.client_transactions,
        )
        result = mortgage.post_posting_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertEqual(expected_result, result)
        mock_move_balance_custom_instructions.assert_called_once_with(
            amount=Decimal("10"),
            denomination="GBP",
            vault_account=mock_vault.account_id,
            balance_address=mortgage.lending_addresses.INTEREST_DUE,
        )
        mock_get_interest_to_revert.assert_called_once_with(
            sentinel.balances_dummy_balances_observation, "GBP"
        )
        mock_get_interest_adjustment_custom_instructions.assert_called_once_with(
            amount=Decimal("5"),
            denomination="GBP",
            vault_account=mock_vault.account_id,
            interest_received_account=sentinel.interest_received_account,
        )

    @patch.object(mortgage, "_process_payment")
    def test_balance_delta_negative_returns_instructions_and_notifications(
        self,
        mock_process_payment: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        # expected values
        expected_cis = [SentinelCustomInstruction("process_payment")]
        expected_notification_directives = [SentinelAccountNotificationDirective("process_payment")]

        # construct mocks
        mock_vault = self.create_mock()
        mock_is_force_override.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={**self.common_get_param_return_values}
        )
        mock_process_payment.return_value = (expected_cis, expected_notification_directives)

        posting_instructions = [self.inbound_hard_settlement(amount=Decimal("10"))]

        # construct expected result
        expected_result = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_cis,  # type: ignore
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
            account_notification_directives=expected_notification_directives,  # type: ignore
        )

        # run function
        hook_args = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=posting_instructions,
            client_transactions=sentinel.client_transactions,
        )
        result = mortgage.post_posting_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertEqual(expected_result, result)
        mock_process_payment.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            denomination="GBP",
        )


@patch.object(mortgage.close_loan, "does_repayment_fully_repay_loan")
@patch.object(mortgage.overpayment, "OverpaymentFeature")
@patch.object(mortgage.payments, "generate_repayment_postings")
class ProcessPaymentTest(MortgageTestBase):
    balances_observation_fetchers_mapping = {
        mortgage.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live_balances")
    }

    def test_process_payment_partial_repayment_does_not_generate_closure_notification(
        self,
        mock_generate_repayment_postings: MagicMock,
        mock_overpayment_feature: MagicMock,
        mock_does_repayment_fully_repay_loan: MagicMock,
    ):
        mock_does_repayment_fully_repay_loan.return_value = False
        mock_generate_repayment_postings.return_value = [sentinel.repayment_ci]
        mock_vault = self.create_mock()

        # construct expected result
        expected_cis = [sentinel.repayment_ci]
        expected_notifications: list[AccountNotificationDirective] = []

        # run function
        result_cis, result_notifications = mortgage._process_payment(
            vault=mock_vault,
            hook_arguments=sentinel.hook_arguments,
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )

        self.assertListEqual(result_cis, expected_cis)
        self.assertListEqual(result_notifications, expected_notifications)
        mock_generate_repayment_postings.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=sentinel.hook_arguments,
            overpayment_features=[
                mock_overpayment_feature,
                mortgage.overpayment_allowance.OverpaymentAllowanceFeature,
            ],
        )
        mock_does_repayment_fully_repay_loan.assert_called_once_with(
            repayment_posting_instructions=expected_cis,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            account_id="default_account",
            payment_addresses=mortgage.lending_addresses.ALL_OUTSTANDING,
        )

    @patch.object(mortgage, "_handle_early_repayment_fee")
    @patch.object(
        mortgage.interest_capitalisation, "handle_overpayments_to_penalties_pending_capitalisation"
    )
    @patch.object(mortgage.utils, "get_parameter")
    def test_process_payment_full_repayment_generates_closure_notification(
        self,
        mock_get_parameter: MagicMock,
        mock_handle_overpayments_to_penalties_pending_capitalisation: MagicMock,
        mock_handle_early_repayment_fee: MagicMock,
        mock_generate_repayment_postings: MagicMock,
        mock_overpayment_feature: MagicMock,
        mock_does_repayment_fully_repay_loan: MagicMock,
    ):
        mock_does_repayment_fully_repay_loan.return_value = True
        mock_generate_repayment_postings.return_value = [sentinel.repayment_ci]
        mock_handle_early_repayment_fee.return_value = []
        mock_handle_overpayments_to_penalties_pending_capitalisation.return_value = []
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={mortgage.PARAM_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT: "dummy_account"}
        )
        mock_vault = self.create_mock()

        # construct expected result
        expected_cis = [sentinel.repayment_ci]
        expected_notifications: list[AccountNotificationDirective] = [
            AccountNotificationDirective(
                notification_type="MORTGAGE_CLOSURE",
                notification_details={"account_id": str(mock_vault.account_id)},
            )
        ]

        # run function
        result_cis, result_notifications = mortgage._process_payment(
            vault=mock_vault,
            hook_arguments=sentinel.hook_arguments,
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )

        self.assertListEqual(result_cis, expected_cis)
        self.assertListEqual(result_notifications, expected_notifications)
        mock_generate_repayment_postings.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=sentinel.hook_arguments,
            overpayment_features=[
                mock_overpayment_feature,
                mortgage.overpayment_allowance.OverpaymentAllowanceFeature,
            ],
        )
        mock_does_repayment_fully_repay_loan.assert_called_once_with(
            repayment_posting_instructions=expected_cis,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            account_id="default_account",
            payment_addresses=mortgage.lending_addresses.ALL_OUTSTANDING,
        )
        mock_get_parameter.assert_called_once_with(
            vault=mock_vault, name=mortgage.PARAM_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT
        )

    @patch.object(mortgage, "_handle_early_repayment_fee")
    @patch.object(
        mortgage.interest_capitalisation, "handle_overpayments_to_penalties_pending_capitalisation"
    )
    @patch.object(mortgage.utils, "get_parameter")
    def test_process_payment_fetches_balances_if_required(
        self,
        mock_get_parameter: MagicMock,
        mock_handle_overpayments_to_penalties_pending_capitalisation: MagicMock,
        mock_handle_early_repayment_fee: MagicMock,
        mock_generate_repayment_postings: MagicMock,
        mock_overpayment_feature: MagicMock,
        mock_does_repayment_fully_repay_loan: MagicMock,
    ):
        mock_does_repayment_fully_repay_loan.return_value = True
        mock_generate_repayment_postings.return_value = [sentinel.repayment_ci]
        mock_handle_early_repayment_fee.return_value = []
        mock_handle_overpayments_to_penalties_pending_capitalisation.return_value = []
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={mortgage.PARAM_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT: "dummy_account"}
        )
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                mortgage.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live_balances")
            }
        )

        # construct expected result
        expected_cis = [sentinel.repayment_ci]
        expected_notifications: list[AccountNotificationDirective] = [
            AccountNotificationDirective(
                notification_type="MORTGAGE_CLOSURE",
                notification_details={"account_id": str(mock_vault.account_id)},
            )
        ]

        # run function
        result_cis, result_notifications = mortgage._process_payment(
            vault=mock_vault,
            hook_arguments=sentinel.hook_arguments,
            denomination=sentinel.denomination,
        )

        self.assertListEqual(result_cis, expected_cis)
        self.assertListEqual(result_notifications, expected_notifications)
        mock_generate_repayment_postings.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=sentinel.hook_arguments,
            overpayment_features=[
                mock_overpayment_feature,
                mortgage.overpayment_allowance.OverpaymentAllowanceFeature,
            ],
        )
        mock_does_repayment_fully_repay_loan.assert_called_once_with(
            repayment_posting_instructions=expected_cis,
            balances=sentinel.balances_live_balances,
            denomination=sentinel.denomination,
            account_id="default_account",
            payment_addresses=mortgage.lending_addresses.ALL_OUTSTANDING,
        )
        mock_get_parameter.assert_called_once_with(
            vault=mock_vault, name=mortgage.PARAM_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT
        )

    @patch.object(mortgage, "_handle_early_repayment_fee")
    @patch.object(
        mortgage.interest_capitalisation, "handle_overpayments_to_penalties_pending_capitalisation"
    )
    @patch.object(mortgage.utils, "get_parameter")
    def test_process_payment_generates_early_repayment_fee_instructions(
        self,
        mock_get_parameter: MagicMock,
        mock_handle_overpayments_to_penalties_pending_capitalisation: MagicMock,
        mock_handle_early_repayment_fee: MagicMock,
        mock_generate_repayment_postings: MagicMock,
        mock_overpayment_feature: MagicMock,
        mock_does_repayment_fully_repay_loan: MagicMock,
    ):
        mock_does_repayment_fully_repay_loan.return_value = True
        mock_generate_repayment_postings.return_value = [sentinel.repayment_ci]
        mock_handle_early_repayment_fee.return_value = [sentinel.early_repayment_fees_ci]
        mock_handle_overpayments_to_penalties_pending_capitalisation.return_value = [
            sentinel.penalties_pending_capitalisation_ci
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={mortgage.PARAM_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT: "dummy_account"}
        )
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                mortgage.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live_balances")
            }
        )

        # construct expected result
        expected_cis = [
            sentinel.repayment_ci,
            sentinel.penalties_pending_capitalisation_ci,
            sentinel.early_repayment_fees_ci,
        ]
        expected_notifications: list[AccountNotificationDirective] = [
            AccountNotificationDirective(
                notification_type="MORTGAGE_CLOSURE",
                notification_details={"account_id": str(mock_vault.account_id)},
            )
        ]

        # run function
        result_cis, result_notifications = mortgage._process_payment(
            vault=mock_vault,
            hook_arguments=sentinel.hook_arguments,
            denomination=sentinel.denomination,
        )

        self.assertListEqual(result_cis, expected_cis)
        self.assertListEqual(result_notifications, expected_notifications)
        mock_generate_repayment_postings.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=sentinel.hook_arguments,
            overpayment_features=[
                mock_overpayment_feature,
                mortgage.overpayment_allowance.OverpaymentAllowanceFeature,
            ],
        )
        mock_does_repayment_fully_repay_loan.assert_called_once_with(
            repayment_posting_instructions=expected_cis,
            balances=sentinel.balances_live_balances,
            denomination=sentinel.denomination,
            account_id="default_account",
            payment_addresses=mortgage.lending_addresses.ALL_OUTSTANDING,
        )
        mock_get_parameter.assert_called_once_with(
            vault=mock_vault, name=mortgage.PARAM_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT
        )
        mock_handle_early_repayment_fee.assert_called_once_with(
            repayment_posting_instructions=expected_cis,
            balances=sentinel.balances_live_balances,
            account_id="default_account",
            early_repayment_fee_account="dummy_account",
            denomination=sentinel.denomination,
        )
