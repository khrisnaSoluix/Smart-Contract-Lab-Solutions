# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# library
import library.line_of_credit.supervisors.template.line_of_credit_supervisor as line_of_credit_supervisor  # noqa: E501
from library.line_of_credit.test.unit.test_line_of_credit_supervisor_common import (
    LineOfCreditSupervisorTestBase,
)

# features
import library.features.common.fetchers as fetchers

# contracts api
from contracts_api import (
    Balance,
    BalanceCoordinate,
    BalanceDefaultDict,
    Phase,
    PrePostingHookResult,
    RejectionReason,
    SupervisorPrePostingHookArguments,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    DEFAULT_DATETIME,
    DEFAULT_DENOMINATION,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    Rejection,
    SupervisorPrePostingHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelRejection,
)


@patch.object(line_of_credit_supervisor, "_get_loc_and_loan_supervisee_vault_objects")
@patch.object(line_of_credit_supervisor.utils, "is_force_override")
class PrePostingTest(LineOfCreditSupervisorTestBase):
    def test_rejection_if_no_loc_account_is_associated_to_the_plan(
        self,
        mock_is_force_override: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = (None, None)

        hook_arguments = SupervisorPrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            supervisee_posting_instructions={"default_account": sentinel.loc_posting_instructions},
            supervisee_client_transactions={},
        )

        result = line_of_credit_supervisor.pre_posting_hook(sentinel.vault, hook_arguments)
        expected_result = SupervisorPrePostingHookResult(
            rejection=Rejection(
                message="Cannot process postings until a supervisee with an alias "
                "line_of_credit is associated to the plan",
                reason_code=RejectionReason.CLIENT_CUSTOM_REASON,
            )
        )
        self.assertEqual(result, expected_result)

        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)
        mock_is_force_override.assert_not_called()

    def test_is_force_override_returns_none(
        self,
        mock_is_force_override: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = (
            self.create_supervisee_mock(),
            sentinel.loan_account_vaults,
        )
        mock_is_force_override.return_value = True

        hook_arguments = SupervisorPrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            supervisee_posting_instructions={"default_account": sentinel.loc_posting_instructions},
            supervisee_client_transactions={},
        )

        result = line_of_credit_supervisor.pre_posting_hook(sentinel.vault, hook_arguments)
        self.assertIsNone(result)

        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)
        mock_is_force_override.assert_called_once_with(
            posting_instructions=sentinel.loc_posting_instructions
        )

    def test_supervisee_rejection(
        self,
        mock_is_force_override: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = (
            self.create_supervisee_mock(
                supervisee_hook_result=PrePostingHookResult(
                    rejection=SentinelRejection("supervisee_rejection")
                )
            ),
            sentinel.loan_account_vaults,
        )
        mock_is_force_override.return_value = False

        hook_arguments = SupervisorPrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            supervisee_posting_instructions={"default_account": sentinel.loc_posting_instructions},
            supervisee_client_transactions={},
        )

        result = line_of_credit_supervisor.pre_posting_hook(sentinel.vault, hook_arguments)
        expected_result = SupervisorPrePostingHookResult(
            rejection=SentinelRejection("supervisee_rejection")
        )

        self.assertEqual(result, expected_result)

        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)
        mock_is_force_override.assert_called_once_with(
            posting_instructions=sentinel.loc_posting_instructions
        )

    @patch.object(line_of_credit_supervisor, "_validate_repayment")
    @patch.object(line_of_credit_supervisor, "_get_loan_vaults_for_repayment_distribution")
    @patch.object(line_of_credit_supervisor.common_parameters, "get_denomination_parameter")
    @patch.object(line_of_credit_supervisor.utils, "balance_at_coordinates")
    @patch.object(line_of_credit_supervisor, "_get_application_precision_parameter")
    def test_invalid_repayment_is_rejected(
        self,
        mock_get_application_precision_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_denomination_parameter: MagicMock,
        mock_get_loan_vaults_for_repayment_distribution: MagicMock,
        mock_validate_repayment: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_loc_vault = self.create_supervisee_mock(
            balances_observation_fetchers_mapping={
                fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("loc_balances")
            },
            supervisee_hook_result=PrePostingHookResult(),
        )
        mock_loan_vault_1 = self.create_supervisee_mock(
            balances_observation_fetchers_mapping={
                fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("loan_1_balances")
            },
        )
        mock_loan_vault_2 = self.create_supervisee_mock(
            balances_observation_fetchers_mapping={
                fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("loan_2_balances")
            },
        )
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = (
            mock_loc_vault,
            sentinel.loan_vaults,
        )
        mock_is_force_override.return_value = False
        mock_get_denomination_parameter.return_value = sentinel.denomination
        mock_balance_at_coordinates.return_value = Decimal("-100")
        mock_get_loan_vaults_for_repayment_distribution.return_value = [
            mock_loan_vault_1,
            mock_loan_vault_2,
        ]
        mock_validate_repayment.return_value = SentinelRejection("repayment_rejection")
        mock_get_application_precision_parameter.return_value = sentinel.application_precision_param

        posting_instructions = [self.inbound_hard_settlement(amount=Decimal("100"))]

        hook_arguments = SupervisorPrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            supervisee_posting_instructions={"default_account": posting_instructions},
            supervisee_client_transactions={},
        )

        expected_result = SupervisorPrePostingHookResult(
            rejection=SentinelRejection("repayment_rejection")
        )

        result = line_of_credit_supervisor.pre_posting_hook(sentinel.vault, hook_arguments)

        self.assertEqual(result, expected_result)

        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)
        mock_is_force_override.assert_called_once_with(posting_instructions=posting_instructions)
        mock_get_denomination_parameter.assert_called_once_with(vault=mock_loc_vault)
        mock_balance_at_coordinates.assert_called_once_with(
            balances=BalanceDefaultDict(
                mapping={
                    BalanceCoordinate(
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        denomination=DEFAULT_DENOMINATION,
                        phase=Phase.COMMITTED,
                    ): Balance(credit=Decimal("100"), debit=Decimal("0"), net=Decimal("-100"))
                }
            ),
            denomination=sentinel.denomination,
        )
        mock_get_loan_vaults_for_repayment_distribution.assert_called_once_with(
            loan_vaults=sentinel.loan_vaults, posting_instruction=posting_instructions[0]
        )
        mock_validate_repayment.assert_called_once_with(
            loc_vault=mock_loc_vault,
            all_supervisee_balances=[
                sentinel.balances_loc_balances,
                sentinel.balances_loan_1_balances,
                sentinel.balances_loan_2_balances,
            ],
            repayment_amount=Decimal("100"),
            denomination=sentinel.denomination,
            rounding_precision=sentinel.application_precision_param,
        )

    @patch.object(line_of_credit_supervisor, "_validate_repayment")
    @patch.object(line_of_credit_supervisor, "_get_loan_vaults_for_repayment_distribution")
    @patch.object(line_of_credit_supervisor.common_parameters, "get_denomination_parameter")
    @patch.object(line_of_credit_supervisor.utils, "balance_at_coordinates")
    def test_invalid_target_account_id_is_rejected(
        self,
        mock_balance_at_coordinates: MagicMock,
        mock_get_denomination_parameter: MagicMock,
        mock_get_loan_vaults_for_repayment_distribution: MagicMock,
        mock_validate_repayment: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_loc_vault = self.create_supervisee_mock(
            balances_observation_fetchers_mapping={
                fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("loc_balances")
            },
            supervisee_hook_result=PrePostingHookResult(),
        )
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = (
            mock_loc_vault,
            sentinel.loan_vaults,
        )
        mock_is_force_override.return_value = False
        mock_get_denomination_parameter.return_value = sentinel.denomination
        mock_balance_at_coordinates.return_value = Decimal("-100")
        mock_get_loan_vaults_for_repayment_distribution.return_value = []

        posting_instructions = [
            self.inbound_hard_settlement(
                amount=Decimal("100"),
                instruction_details={"target_account_id": "invalid account id"},
            )
        ]

        hook_arguments = SupervisorPrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            supervisee_posting_instructions={"default_account": posting_instructions},
            supervisee_client_transactions={},
        )

        expected_result = SupervisorPrePostingHookResult(
            rejection=Rejection(
                message="The target account id invalid account id does not exist",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )

        result = line_of_credit_supervisor.pre_posting_hook(sentinel.vault, hook_arguments)

        self.assertEqual(result, expected_result)

        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)
        mock_is_force_override.assert_called_once_with(posting_instructions=posting_instructions)
        mock_get_denomination_parameter.assert_called_once_with(vault=mock_loc_vault)
        mock_balance_at_coordinates.assert_called_once_with(
            balances=BalanceDefaultDict(
                mapping={
                    BalanceCoordinate(
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        denomination=DEFAULT_DENOMINATION,
                        phase=Phase.COMMITTED,
                    ): Balance(credit=Decimal("100"), debit=Decimal("0"), net=Decimal("-100"))
                }
            ),
            denomination=sentinel.denomination,
        )
        mock_get_loan_vaults_for_repayment_distribution.assert_called_once_with(
            loan_vaults=sentinel.loan_vaults, posting_instruction=posting_instructions[0]
        )
        mock_validate_repayment.assert_not_called()

    @patch.object(line_of_credit_supervisor, "_validate_repayment")
    @patch.object(line_of_credit_supervisor, "_get_loan_vaults_for_repayment_distribution")
    @patch.object(line_of_credit_supervisor.common_parameters, "get_denomination_parameter")
    @patch.object(line_of_credit_supervisor.utils, "balance_at_coordinates")
    @patch.object(line_of_credit_supervisor, "_get_application_precision_parameter")
    def test_valid_repayment(
        self,
        mock_get_application_precision_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_denomination_parameter: MagicMock,
        mock_get_loan_vaults_for_repayment_distribution: MagicMock,
        mock_validate_repayment: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_loc_vault = self.create_supervisee_mock(
            balances_observation_fetchers_mapping={
                fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("loc_balances")
            },
            supervisee_hook_result=PrePostingHookResult(),
        )
        mock_loan_vault_1 = self.create_supervisee_mock(
            balances_observation_fetchers_mapping={
                fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("loan_1_balances")
            },
        )
        mock_loan_vault_2 = self.create_supervisee_mock(
            balances_observation_fetchers_mapping={
                fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("loan_2_balances")
            },
        )
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = (
            mock_loc_vault,
            sentinel.loan_vaults,
        )
        mock_is_force_override.return_value = False
        mock_get_denomination_parameter.return_value = sentinel.denomination
        mock_balance_at_coordinates.return_value = Decimal("-100")
        mock_get_loan_vaults_for_repayment_distribution.return_value = [
            mock_loan_vault_1,
            mock_loan_vault_2,
        ]
        mock_validate_repayment.return_value = None
        mock_get_application_precision_parameter.return_value = sentinel.application_precision_param

        posting_instructions = [self.inbound_hard_settlement(amount=Decimal("100"))]

        hook_arguments = SupervisorPrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            supervisee_posting_instructions={"default_account": posting_instructions},
            supervisee_client_transactions={},
        )

        result = line_of_credit_supervisor.pre_posting_hook(sentinel.vault, hook_arguments)

        self.assertIsNone(result)

        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)
        mock_is_force_override.assert_called_once_with(posting_instructions=posting_instructions)
        mock_get_denomination_parameter.assert_called_once_with(vault=mock_loc_vault)
        mock_balance_at_coordinates.assert_called_once_with(
            balances=BalanceDefaultDict(
                mapping={
                    BalanceCoordinate(
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        denomination=DEFAULT_DENOMINATION,
                        phase=Phase.COMMITTED,
                    ): Balance(credit=Decimal("100"), debit=Decimal("0"), net=Decimal("-100"))
                }
            ),
            denomination=sentinel.denomination,
        )
        mock_get_loan_vaults_for_repayment_distribution.assert_called_once_with(
            loan_vaults=sentinel.loan_vaults, posting_instruction=posting_instructions[0]
        )
        mock_validate_repayment.assert_called_once_with(
            loc_vault=mock_loc_vault,
            all_supervisee_balances=[
                sentinel.balances_loc_balances,
                sentinel.balances_loan_1_balances,
                sentinel.balances_loan_2_balances,
            ],
            repayment_amount=Decimal("100"),
            denomination=sentinel.denomination,
            rounding_precision=sentinel.application_precision_param,
        )


@patch.object(line_of_credit_supervisor, "_get_loc_and_loan_supervisee_vault_objects")
@patch.object(line_of_credit_supervisor.utils, "is_force_override")
@patch.object(line_of_credit_supervisor.common_parameters, "get_denomination_parameter")
@patch.object(line_of_credit_supervisor.utils, "balance_at_coordinates")
@patch.object(line_of_credit_supervisor.maximum_outstanding_loans, "validate")
class LoanCreationTest(LineOfCreditSupervisorTestBase):
    def test_max_outstanding_loans_rejection_is_returned(
        self,
        mock_validate_maximum_outstanding_loans: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_denomination_parameter: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_loc_vault = self.create_supervisee_mock(supervisee_hook_result=PrePostingHookResult())
        mock_loan_vaults = [
            sentinel.loan_1,
            sentinel.loan_2,
        ]
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = (
            mock_loc_vault,
            mock_loan_vaults,
        )
        mock_is_force_override.return_value = False
        mock_get_denomination_parameter.return_value = sentinel.denomination
        mock_balance_at_coordinates.return_value = Decimal("100")
        mock_validate_maximum_outstanding_loans.return_value = SentinelRejection(
            "Max outstanding loans rejection"
        )

        posting_instructions = [self.outbound_hard_settlement(amount=Decimal("100"))]

        hook_arguments = SupervisorPrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            supervisee_posting_instructions={"default_account": posting_instructions},
            supervisee_client_transactions={},
        )

        expected = SupervisorPrePostingHookResult(
            rejection=SentinelRejection("Max outstanding loans rejection")
        )

        result = line_of_credit_supervisor.pre_posting_hook(sentinel.vault, hook_arguments)
        self.assertEqual(result, expected)

        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)
        mock_is_force_override.assert_called_once_with(posting_instructions=posting_instructions)
        mock_get_denomination_parameter.assert_called_once_with(vault=mock_loc_vault)
        mock_balance_at_coordinates.assert_called_once_with(
            balances=BalanceDefaultDict(
                mapping={
                    BalanceCoordinate(
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        denomination=DEFAULT_DENOMINATION,
                        phase=Phase.COMMITTED,
                    ): Balance(credit=Decimal("0"), debit=Decimal("100"), net=Decimal("100"))
                }
            ),
            denomination=sentinel.denomination,
        )
        mock_validate_maximum_outstanding_loans.assert_called_once_with(
            main_vault=mock_loc_vault, loans=mock_loan_vaults
        )

    @patch.object(line_of_credit_supervisor.credit_limit, "validate")
    def test_loan_creation_above_credit_limit_is_rejected(
        self,
        mock_credit_limit_validate: MagicMock,
        mock_validate_maximum_outstanding_loans: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_denomination_parameter: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_loc_vault = self.create_supervisee_mock(supervisee_hook_result=PrePostingHookResult())
        mock_loan_vaults = [
            sentinel.loan_1,
            sentinel.loan_2,
        ]
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = (
            mock_loc_vault,
            mock_loan_vaults,
        )
        mock_is_force_override.return_value = False
        mock_get_denomination_parameter.return_value = sentinel.denomination
        mock_balance_at_coordinates.return_value = Decimal("100")
        mock_validate_maximum_outstanding_loans.return_value = None
        mock_credit_limit_validate.return_value = SentinelRejection("Credit limit rejection")

        posting_instruction = self.outbound_hard_settlement(amount=Decimal("100"))
        posting_instructions = [posting_instruction]

        hook_arguments = SupervisorPrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            supervisee_posting_instructions={"default_account": posting_instructions},
            supervisee_client_transactions={},
        )

        expected = SupervisorPrePostingHookResult(
            rejection=SentinelRejection("Credit limit rejection")
        )

        result = line_of_credit_supervisor.pre_posting_hook(sentinel.vault, hook_arguments)
        self.assertEqual(result, expected)

        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)
        mock_is_force_override.assert_called_once_with(posting_instructions=posting_instructions)
        mock_get_denomination_parameter.assert_called_once_with(vault=mock_loc_vault)
        mock_balance_at_coordinates.assert_called_once_with(
            balances=BalanceDefaultDict(
                mapping={
                    BalanceCoordinate(
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        denomination=DEFAULT_DENOMINATION,
                        phase=Phase.COMMITTED,
                    ): Balance(credit=Decimal("0"), debit=Decimal("100"), net=Decimal("100"))
                }
            ),
            denomination=sentinel.denomination,
        )
        mock_validate_maximum_outstanding_loans.assert_called_once_with(
            main_vault=mock_loc_vault, loans=mock_loan_vaults
        )
        mock_credit_limit_validate.assert_called_once_with(
            main_vault=mock_loc_vault,
            loans=mock_loan_vaults,
            posting_instruction=posting_instruction,
            non_repayable_addresses=line_of_credit_supervisor.NON_REPAYABLE_ADDRESSES,
        )
