# standard libs
from decimal import Decimal
from unittest.mock import patch, sentinel

# library
import library.line_of_credit.supervisors.template.line_of_credit_supervisor as line_of_credit_supervisor  # noqa: E501
from library.line_of_credit.test.unit.test_line_of_credit_supervisor_common import (
    LineOfCreditSupervisorTestBase,
)

# contracts api
from contracts_api import PostingInstructionsDirective, SupervisorPostPostingHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    SupervisorPostPostingHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelPostingInstructionsDirective,
)


class PostPostingTest(LineOfCreditSupervisorTestBase):
    def setUp(self) -> None:
        self.mock_get_loc_and_loan_supervisee_vault_objects = patch.object(
            line_of_credit_supervisor, "_get_loc_and_loan_supervisee_vault_objects"
        ).start()
        self.mock_get_denomination_parameter = patch.object(
            line_of_credit_supervisor.common_parameters, "get_denomination_parameter"
        ).start()
        self.mock_is_force_override = patch.object(
            line_of_credit_supervisor.utils, "is_force_override"
        ).start()
        self.mock_balance_at_coordinates = patch.object(
            line_of_credit_supervisor.utils, "balance_at_coordinates"
        ).start()
        self.mock_get_loan_vaults_for_repayment_distribution = patch.object(
            line_of_credit_supervisor, "_get_loan_vaults_for_repayment_distribution"
        ).start()
        self.mock_sort_supervisees = patch.object(
            line_of_credit_supervisor.supervisor_utils, "sort_supervisees"
        ).start()
        self.mock_handle_repayment = patch.object(
            line_of_credit_supervisor, "_handle_repayment"
        ).start()

        self.mock_loan_1 = self.create_supervisee_mock(account_id="loan_1")
        self.mock_loan_2 = self.create_supervisee_mock(account_id="loan_2")
        self.mock_loc = self.create_supervisee_mock(account_id="loc")

        self.mock_get_loc_and_loan_supervisee_vault_objects.return_value = (
            self.mock_loc,
            [self.mock_loan_1, self.mock_loan_2],
        )
        self.mock_get_denomination_parameter.return_value = sentinel.denomination
        self.mock_is_force_override.return_value = False
        self.mock_balance_at_coordinates.return_value = Decimal("-100")
        self.mock_get_loan_vaults_for_repayment_distribution.return_value = [
            self.mock_loan_1,
            self.mock_loan_2,
        ]
        self.mock_sort_supervisees.return_value = [
            self.mock_loc,
            self.mock_loan_1,
            self.mock_loan_2,
        ]
        self.posting_instructions = [self.outbound_hard_settlement(amount=Decimal("100"))]
        self.repayment_posting_directives: dict[str, list[PostingInstructionsDirective]] = {
            self.mock_loc.account_id: [SentinelPostingInstructionsDirective("loc_instructions")],
            self.mock_loan_1.account_id: [
                SentinelPostingInstructionsDirective("loan_1_instructions")
            ],
            self.mock_loan_2.account_id: [
                SentinelPostingInstructionsDirective("loan_2_instructions")
            ],
        }
        self.mock_handle_repayment.return_value = (self.repayment_posting_directives, {})

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_is_force_override_returns_none(self):
        self.mock_is_force_override.return_value = True

        hook_arguments = SupervisorPostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            supervisee_posting_instructions={"loc": sentinel.loc_posting_instructions},
            supervisee_client_transactions={},
        )

        result = line_of_credit_supervisor.post_posting_hook(sentinel.vault, hook_arguments)
        self.assertIsNone(result)

        self.mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(
            vault=sentinel.vault
        )
        self.mock_get_denomination_parameter.assert_called_once_with(vault=self.mock_loc)
        self.mock_balance_at_coordinates.assert_not_called()
        self.mock_get_loan_vaults_for_repayment_distribution.assert_not_called()
        self.mock_sort_supervisees.assert_not_called()
        self.mock_handle_repayment.assert_not_called()

    def test_posting_is_debit(self):
        self.mock_balance_at_coordinates.return_value = Decimal("100")

        expected_result = SupervisorPostPostingHookResult(
            supervisee_posting_instructions_directives={},
            supervisee_account_notification_directives={},
        )

        hook_arguments = SupervisorPostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            supervisee_posting_instructions={"loc": self.posting_instructions},
            supervisee_client_transactions={},
        )

        result = line_of_credit_supervisor.post_posting_hook(sentinel.vault, hook_arguments)
        self.assertEqual(result, expected_result)

        self.mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(
            vault=sentinel.vault
        )
        self.mock_get_denomination_parameter.assert_called_once_with(vault=self.mock_loc)
        self.mock_is_force_override.assert_called_once_with(
            posting_instructions=self.posting_instructions
        )
        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=self.posting_instructions[0].balances(), denomination=sentinel.denomination
        )
        self.mock_get_loan_vaults_for_repayment_distribution.assert_not_called()
        self.mock_sort_supervisees.assert_not_called()
        self.mock_handle_repayment.assert_not_called()

    def test_valid_repayment(self):
        expected_result = SupervisorPostPostingHookResult(
            supervisee_posting_instructions_directives=self.repayment_posting_directives,
            supervisee_account_notification_directives={},
        )

        hook_arguments = SupervisorPostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            supervisee_posting_instructions={"loc": self.posting_instructions},
            supervisee_client_transactions={},
        )

        result = line_of_credit_supervisor.post_posting_hook(sentinel.vault, hook_arguments)
        self.assertEqual(result, expected_result)

        self.mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(
            vault=sentinel.vault
        )
        self.mock_get_denomination_parameter.assert_called_once_with(vault=self.mock_loc)
        self.mock_is_force_override.assert_called_once_with(
            posting_instructions=self.posting_instructions
        )
        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=self.posting_instructions[0].balances(), denomination=sentinel.denomination
        )
        self.mock_get_loan_vaults_for_repayment_distribution.assert_called_once_with(
            loan_vaults=[self.mock_loan_1, self.mock_loan_2],
            posting_instruction=self.posting_instructions[0],
        )
        self.mock_sort_supervisees.assert_called_once_with(
            supervisees=[self.mock_loc, self.mock_loan_1, self.mock_loan_2]
        )
        self.mock_handle_repayment.assert_called_once_with(
            hook_arguments=hook_arguments,
            sorted_repayment_targets=[self.mock_loc, self.mock_loan_1, self.mock_loan_2],
            loc_vault=self.mock_loc,
            denomination=sentinel.denomination,
        )
