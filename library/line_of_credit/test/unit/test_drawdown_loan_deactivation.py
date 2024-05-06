# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from decimal import Decimal
from unittest.mock import call, patch, sentinel

# library
from library.line_of_credit.contracts.template import drawdown_loan
from library.line_of_credit.test.unit.test_drawdown_loan_common import (
    DEFAULT_DATETIME,
    DrawdownLoanTestBase,
)

# features
from library.features.common.fetchers import LIVE_BALANCES_BOF_ID
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    CustomInstruction,
    DeactivationHookArguments,
    RejectionReason,
    Tside,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DeactivationHookResult,
    PostingInstructionsDirective,
    Rejection,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelCustomInstruction,
    SentinelPosting,
)


class DrawdownLoanDeactivationTest(DrawdownLoanTestBase):
    def setUp(self) -> None:
        self.mock_get_parameter = patch.object(drawdown_loan.utils, "get_parameter").start()
        self.mock_reject_closure_when_outstanding_debt = patch.object(
            drawdown_loan.close_loan, "reject_closure_when_outstanding_debt"
        ).start()
        self.mock_net_balances = patch.object(drawdown_loan.close_loan, "net_balances").start()
        self.mock_update_inflight_balances = patch.object(
            drawdown_loan.utils, "update_inflight_balances"
        ).start()
        self.mock_balance_at_coordinates = patch.object(
            drawdown_loan.utils, "balance_at_coordinates"
        ).start()
        self.mock_create_postings = patch.object(drawdown_loan.utils, "create_postings").start()
        self.mock_net_aggregate_emi = patch.object(drawdown_loan, "_net_aggregate_emi").start()
        self.mock_get_original_principal_custom_instructions = patch.object(
            drawdown_loan, "_get_original_principal_custom_instructions"
        ).start()

        self.balance_observation = SentinelBalancesObservation("dummy_balance_observation")
        self.mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={LIVE_BALANCES_BOF_ID: self.balance_observation}
        )

        common_param_return_values = {
            "denomination": sentinel.denomination,
            "line_of_credit_account_id": sentinel.loc_account_id,
            "principal": sentinel.principal,
        }
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=common_param_return_values
        )

        self.mock_reject_closure_when_outstanding_debt.return_value = None
        self.net_balances_instructions = [SentinelCustomInstruction("net_balances")]
        self.mock_net_balances.return_value = self.net_balances_instructions
        self.mock_update_inflight_balances.return_value = (
            sentinel.balances_after_closure_instructions
        )
        self.mock_balance_at_coordinates.return_value = (
            sentinel.internal_contra_amount_after_closure_instructions
        )

        self.repayments_posting = SentinelPosting("repayments")
        # This is required to prevent validation error when constructing
        # PostingInstructionsDirective
        self.repayments_posting.amount = Decimal("0")
        self.mock_create_postings.return_value = [self.repayments_posting]

        self.net_aggregate_emi_posting = SentinelPosting("net_aggregate_emi")
        # This is required to prevent validation error when constructing
        # PostingInstructionsDirective
        self.net_aggregate_emi_posting.amount = Decimal("0")
        self.mock_net_aggregate_emi.return_value = [self.net_aggregate_emi_posting]

        self.net_aggregate_total_original_principal = SentinelCustomInstruction(
            "total_original_principal"
        )

        self.mock_get_original_principal_custom_instructions.return_value = [
            self.net_aggregate_total_original_principal
        ]

        self.addCleanup(patch.stopall)

        return super().setUp()

    def test_reject_when_outstanding_debt(self):
        self.mock_reject_closure_when_outstanding_debt.return_value = Rejection(
            message="The loan cannot be closed until all outstanding debt is repaid",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        expected_result = DeactivationHookResult(
            rejection=Rejection(
                message="The loan cannot be closed until all outstanding debt is repaid",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )

        hook_arguments = DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = drawdown_loan.deactivation_hook(
            vault=self.mock_vault, hook_arguments=hook_arguments
        )

        self.assertEqual(result, expected_result)

        self.mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    vault=self.mock_vault,
                    name=drawdown_loan.common_parameters.PARAM_DENOMINATION,
                    at_datetime=None,
                ),
                call(vault=self.mock_vault, name=drawdown_loan.PARAM_LOC_ACCOUNT_ID),
            ]
        )
        self.mock_reject_closure_when_outstanding_debt.assert_called_once_with(
            balances=self.balance_observation.balances,
            denomination=sentinel.denomination,
            debt_addresses=drawdown_loan.lending_addresses.ALL_OUTSTANDING_SUPERVISOR,
        )
        self.mock_net_balances.assert_not_called()
        self.mock_update_inflight_balances.assert_not_called()
        self.mock_balance_at_coordinates.assert_not_called()
        self.mock_create_postings.assert_not_called()
        self.mock_net_aggregate_emi.assert_not_called()
        self.mock_get_original_principal_custom_instructions.assert_not_called()

    def test_no_outstanding_debt(self):
        loan_closure_custom_instructions = [
            SentinelCustomInstruction("net_balances"),
            CustomInstruction(
                postings=[self.repayments_posting, self.net_aggregate_emi_posting],
                instruction_details={
                    "description": "Clearing all residual balances",
                    "event": "END_OF_LOAN",
                    "force_override": "True",
                },
            ),
            self.net_aggregate_total_original_principal,
        ]
        expected_result = DeactivationHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=loan_closure_custom_instructions,
                    value_datetime=DEFAULT_DATETIME,
                )
            ]
        )

        hook_arguments = DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = drawdown_loan.deactivation_hook(
            vault=self.mock_vault, hook_arguments=hook_arguments
        )

        self.assertEqual(result, expected_result)

        self.mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    vault=self.mock_vault,
                    name=drawdown_loan.common_parameters.PARAM_DENOMINATION,
                    at_datetime=None,
                ),
                call(vault=self.mock_vault, name=drawdown_loan.PARAM_LOC_ACCOUNT_ID),
            ]
        )
        self.mock_reject_closure_when_outstanding_debt.assert_called_once_with(
            balances=self.balance_observation.balances,
            denomination=sentinel.denomination,
            debt_addresses=drawdown_loan.lending_addresses.ALL_OUTSTANDING_SUPERVISOR,
        )
        self.mock_net_balances.assert_called_once_with(
            balances=self.balance_observation.balances,
            denomination=sentinel.denomination,
            account_id=self.mock_vault.account_id,
            residual_cleanup_features=[
                drawdown_loan.overpayment.OverpaymentResidualCleanupFeature,
                drawdown_loan.due_amount_calculation.DueAmountCalculationResidualCleanupFeature,
            ],
        )
        self.mock_update_inflight_balances.assert_called_once_with(
            account_id=self.mock_vault.account_id,
            tside=Tside.ASSET,
            current_balances=self.balance_observation.balances,
            posting_instructions=self.net_balances_instructions,
        )
        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances_after_closure_instructions,
            address=drawdown_loan.lending_addresses.INTERNAL_CONTRA,
            denomination=sentinel.denomination,
        )
        self.mock_create_postings.assert_called_once_with(
            amount=sentinel.internal_contra_amount_after_closure_instructions,
            debit_account=sentinel.loc_account_id,
            credit_account=self.mock_vault.account_id,
            debit_address=DEFAULT_ADDRESS,
            credit_address=drawdown_loan.lending_addresses.INTERNAL_CONTRA,
            denomination=sentinel.denomination,
        )
        self.mock_net_aggregate_emi.assert_called_once_with(
            balances=self.balance_observation.balances,
            loc_account_id=sentinel.loc_account_id,
            denomination=sentinel.denomination,
        )
        self.mock_get_original_principal_custom_instructions.assert_called_once_with(
            principal=sentinel.principal,
            loc_account_id=sentinel.loc_account_id,
            denomination=sentinel.denomination,
            is_closing_loan=True,
        )

    def test_no_instructions(self):
        self.mock_net_balances.return_value = []
        self.mock_create_postings.return_value = []
        self.mock_net_aggregate_emi.return_value = []
        self.mock_get_original_principal_custom_instructions.return_value = []

        hook_arguments = DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = drawdown_loan.deactivation_hook(
            vault=self.mock_vault, hook_arguments=hook_arguments
        )

        self.assertIsNone(result)

        self.mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    vault=self.mock_vault,
                    name=drawdown_loan.common_parameters.PARAM_DENOMINATION,
                    at_datetime=None,
                ),
                call(vault=self.mock_vault, name=drawdown_loan.PARAM_LOC_ACCOUNT_ID),
            ]
        )
        self.mock_reject_closure_when_outstanding_debt.assert_called_once_with(
            balances=self.balance_observation.balances,
            denomination=sentinel.denomination,
            debt_addresses=drawdown_loan.lending_addresses.ALL_OUTSTANDING_SUPERVISOR,
        )
        self.mock_net_balances.assert_called_once_with(
            balances=self.balance_observation.balances,
            denomination=sentinel.denomination,
            account_id=self.mock_vault.account_id,
            residual_cleanup_features=[
                drawdown_loan.overpayment.OverpaymentResidualCleanupFeature,
                drawdown_loan.due_amount_calculation.DueAmountCalculationResidualCleanupFeature,
            ],
        )
        self.mock_update_inflight_balances.assert_called_once_with(
            account_id=self.mock_vault.account_id,
            tside=Tside.ASSET,
            current_balances=self.balance_observation.balances,
            posting_instructions=[],
        )
        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances_after_closure_instructions,
            address=drawdown_loan.lending_addresses.INTERNAL_CONTRA,
            denomination=sentinel.denomination,
        )
        self.mock_create_postings.assert_called_once_with(
            amount=sentinel.internal_contra_amount_after_closure_instructions,
            debit_account=sentinel.loc_account_id,
            credit_account=self.mock_vault.account_id,
            debit_address=DEFAULT_ADDRESS,
            credit_address=drawdown_loan.lending_addresses.INTERNAL_CONTRA,
            denomination=sentinel.denomination,
        )
        self.mock_net_aggregate_emi.assert_called_once_with(
            balances=self.balance_observation.balances,
            loc_account_id=sentinel.loc_account_id,
            denomination=sentinel.denomination,
        )
        self.mock_get_original_principal_custom_instructions.assert_called_once_with(
            principal=sentinel.principal,
            loc_account_id=sentinel.loc_account_id,
            denomination=sentinel.denomination,
            is_closing_loan=True,
        )
