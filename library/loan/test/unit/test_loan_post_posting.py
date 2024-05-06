# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel

# library
from library.loan.contracts.template import loan
from library.loan.test.unit.test_loan_common import DEFAULT_DATETIME, LoanTestBase

# features
import library.features.v4.lending.lending_addresses as lending_addresses
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import DEFAULT_ADDRESS, PostPostingHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import ACCOUNT_ID
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    CustomInstruction,
    PostingInstructionsDirective,
    PostPostingHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    DEFAULT_POSTINGS,
    SentinelAccountNotificationDirective,
    SentinelBalancesObservation,
    SentinelCustomInstruction,
)


@patch.object(loan.utils, "get_parameter")
@patch.object(loan.utils, "is_force_override")
class LoanPostPostingTest(LoanTestBase):
    def test_force_override_returns_none(
        self,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_is_force_override.return_value = True
        hook_args = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[sentinel.postings],
            client_transactions={"cti": sentinel.ClientTransaction},
        )
        result = loan.post_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)

        self.assertIsNone(result)
        mock_get_parameter.assert_not_called()

    @patch.object(loan.utils, "balance_at_coordinates")
    @patch.object(loan.lending_utils, "is_debit")
    @patch.object(loan, "_is_interest_adjustment")
    @patch.object(loan.utils, "create_postings")
    def test_fee_adjustment(
        self,
        mock_create_postings: MagicMock,
        mock_is_interest_adjustment: MagicMock,
        mock_is_debit: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_is_force_override.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )
        mock_is_interest_adjustment.return_value = False
        mock_is_debit.return_value = True
        mock_create_postings.return_value = DEFAULT_POSTINGS

        posting_instructions = [
            self.outbound_hard_settlement(amount=Decimal("1"), instruction_details={"fee": "true"})
        ]
        mock_balance_at_coordinates.return_value = Decimal("1")

        hook_args = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=posting_instructions,
            client_transactions={"cti": sentinel.ClientTransaction},
        )

        expected_ci = CustomInstruction(
            postings=DEFAULT_POSTINGS,
            instruction_details={
                "description": "Adjustment to penalties",
                "event": "ADJUSTMENT_TO_PENALTIES",
            },
            override_all_restrictions=True,
        )

        expected_result = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[expected_ci],
                    value_datetime=DEFAULT_DATETIME,
                )
            ]
        )

        result = loan.post_posting_hook(vault=mock_vault, hook_arguments=hook_args)

        self.assertEqual(result, expected_result)

        mock_create_postings.assert_called_once_with(
            amount=Decimal("1"),
            debit_account=ACCOUNT_ID,
            debit_address=lending_addresses.PENALTIES,
            credit_account=ACCOUNT_ID,
            credit_address=DEFAULT_ADDRESS,
            denomination=sentinel.denomination,
        )
        mock_is_interest_adjustment.assert_called_once_with(posting=posting_instructions[0])

    @patch.object(loan.utils, "balance_at_coordinates")
    @patch.object(loan.lending_utils, "is_debit")
    @patch.object(loan, "_get_interest_to_revert")
    @patch.object(loan, "_is_interest_adjustment")
    @patch.object(loan.utils, "create_postings")
    def test_interest_adjustment(
        self,
        mock_create_postings: MagicMock,
        mock_is_interest_adjustment: MagicMock,
        mock_get_interest_to_revert: MagicMock,
        mock_is_debit: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):

        balance_observation = SentinelBalancesObservation("live")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                loan.fetchers.LIVE_BALANCES_BOF_ID: balance_observation
            }
        )
        mock_is_force_override.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
                "interest_received_account": sentinel.interest_received_account,
            }
        )
        mock_is_interest_adjustment.return_value = True
        mock_is_debit.return_value = True
        mock_create_postings.side_effect = [DEFAULT_POSTINGS, DEFAULT_POSTINGS]
        mock_get_interest_to_revert.return_value = sentinel.interest_to_revert

        posting_instructions = [
            self.outbound_hard_settlement(
                amount=Decimal("1"), instruction_details={"interest": "true"}
            )
        ]
        mock_balance_at_coordinates.return_value = Decimal("1")

        hook_args = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=posting_instructions,
            client_transactions={"cti": sentinel.ClientTransaction},
        )

        expected_ci = CustomInstruction(
            postings=DEFAULT_POSTINGS + DEFAULT_POSTINGS,
            instruction_details={
                "description": "Adjustment to interest_due",
                "event": "ADJUSTMENT_TO_INTEREST_DUE",
            },
            override_all_restrictions=True,
        )
        expected_result = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[expected_ci],
                    value_datetime=DEFAULT_DATETIME,
                )
            ]
        )

        result = loan.post_posting_hook(vault=mock_vault, hook_arguments=hook_args)

        self.assertEqual(result, expected_result)
        mock_get_interest_to_revert.assert_called_once_with(
            balances=sentinel.balances_live, denomination=sentinel.denomination
        )
        mock_create_postings.assert_has_calls(
            calls=[
                call(
                    amount=Decimal("1"),
                    debit_account=ACCOUNT_ID,
                    debit_address=lending_addresses.INTEREST_DUE,
                    credit_account=ACCOUNT_ID,
                    credit_address=DEFAULT_ADDRESS,
                    denomination=sentinel.denomination,
                ),
                call(
                    amount=sentinel.interest_to_revert,
                    debit_account=sentinel.interest_received_account,
                    debit_address=DEFAULT_ADDRESS,
                    credit_account=ACCOUNT_ID,
                    credit_address=lending_addresses.INTEREST_DUE,
                    denomination=sentinel.denomination,
                ),
            ]
        )
        self.assertEqual(mock_create_postings.call_count, 2)
        mock_is_interest_adjustment.assert_called_once_with(posting=posting_instructions[0])

    @patch.object(loan, "_process_payment")
    @patch.object(loan.lending_utils, "is_credit")
    @patch.object(loan.lending_utils, "is_debit")
    def test_repayment_custom_instruction_no_notification(
        self,
        mock_is_debit: MagicMock,
        mock_is_credit: MagicMock,
        mock_process_payment: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_is_debit.return_value = False
        mock_is_credit.return_value = True
        expected_ci = SentinelCustomInstruction("repayment_ci")
        mock_process_payment.return_value = ([expected_ci], [])
        mock_is_force_override.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
            }
        )

        posting_instructions = [self.inbound_hard_settlement(amount=Decimal("1"))]

        hook_args = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=posting_instructions,
            client_transactions={"cti": sentinel.ClientTransaction},
        )

        expected = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[expected_ci], value_datetime=DEFAULT_DATETIME
                )
            ],
            account_notification_directives=[],
        )

        result = loan.post_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)

        self.assertEqual(result, expected)
        mock_process_payment.assert_called_once_with(
            vault=sentinel.vault, hook_arguments=hook_args, denomination=sentinel.denomination
        )

    @patch.object(loan, "_process_payment")
    @patch.object(loan.lending_utils, "is_credit")
    @patch.object(loan.lending_utils, "is_debit")
    def test_repayment_custom_instruction_and_notification(
        self,
        mock_is_debit: MagicMock,
        mock_is_credit: MagicMock,
        mock_process_payment: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_is_debit.return_value = False
        mock_is_credit.return_value = True
        expected_ci = SentinelCustomInstruction("repayment_ci")
        expected_notification = SentinelAccountNotificationDirective("closure")

        mock_process_payment.return_value = ([expected_ci], [expected_notification])
        mock_is_force_override.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
            }
        )

        posting_instructions = [self.inbound_hard_settlement(amount=Decimal("1"))]

        hook_args = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=posting_instructions,
            client_transactions={"cti": sentinel.ClientTransaction},
        )

        expected = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[expected_ci], value_datetime=DEFAULT_DATETIME
                )
            ],
            account_notification_directives=[expected_notification],
        )

        result = loan.post_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)

        self.assertEqual(result, expected)
        mock_process_payment.assert_called_once_with(
            vault=sentinel.vault, hook_arguments=hook_args, denomination=sentinel.denomination
        )

    @patch.object(loan, "_process_payment")
    @patch.object(loan.lending_utils, "is_credit")
    @patch.object(loan.lending_utils, "is_debit")
    def test_repayment_no_custom_instruction_with_notification(
        self,
        mock_is_debit: MagicMock,
        mock_is_credit: MagicMock,
        mock_process_payment: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_is_debit.return_value = False
        mock_is_credit.return_value = True
        expected_notification = SentinelAccountNotificationDirective("closure")

        mock_process_payment.return_value = ([], [expected_notification])
        mock_is_force_override.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
            }
        )

        posting_instructions = [self.inbound_hard_settlement(amount=Decimal("1"))]

        hook_args = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=posting_instructions,
            client_transactions={"cti": sentinel.ClientTransaction},
        )

        expected = PostPostingHookResult(
            posting_instructions_directives=[],
            account_notification_directives=[expected_notification],
        )

        result = loan.post_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)

        self.assertEqual(result, expected)
        mock_process_payment.assert_called_once_with(
            vault=sentinel.vault, hook_arguments=hook_args, denomination=sentinel.denomination
        )

    @patch.object(loan, "_process_payment")
    @patch.object(loan.lending_utils, "is_credit")
    @patch.object(loan.lending_utils, "is_debit")
    def test_repayment_no_custom_instruction_no_notification(
        self,
        mock_is_debit: MagicMock,
        mock_is_credit: MagicMock,
        mock_process_payment: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_is_debit.return_value = False
        mock_is_credit.return_value = True
        mock_process_payment.return_value = ([], [])
        mock_is_force_override.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
            }
        )

        posting_instructions = [self.inbound_hard_settlement(amount=Decimal("1"))]

        hook_args = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=posting_instructions,
            client_transactions={"cti": sentinel.ClientTransaction},
        )

        result = loan.post_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)

        self.assertIsNone(result)
        mock_process_payment.assert_called_once_with(
            vault=sentinel.vault, hook_arguments=hook_args, denomination=sentinel.denomination
        )
