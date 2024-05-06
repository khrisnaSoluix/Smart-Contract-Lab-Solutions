# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import MagicMock, call, patch, sentinel

# library
from library.line_of_credit.contracts.template import drawdown_loan
from library.line_of_credit.test.unit.test_drawdown_loan_common import (
    DEFAULT_DATETIME,
    DrawdownLoanTestBase,
)

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import ActivationHookArguments, BalanceDefaultDict

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    ACCOUNT_ID,
    DEFAULT_HOOK_EXECUTION_ID,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    ActivationHookResult,
    PostingInstructionsDirective,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelCustomInstruction,
)


@patch.object(drawdown_loan, "_get_original_principal_custom_instructions")
@patch.object(drawdown_loan.supervisor_utils, "create_aggregate_posting_instructions")
@patch.object(drawdown_loan.emi, "amortise")
@patch.object(drawdown_loan.disbursement, "get_disbursement_custom_instruction")
@patch.object(drawdown_loan.utils, "get_parameter")
class DrawdownLoanActivationTest(DrawdownLoanTestBase):
    common_param_return_values = {
        "deposit_account": sentinel.deposit_account,
        "principal": sentinel.principal,
        "denomination": sentinel.denomination,
        "line_of_credit_account_id": sentinel.loc_account_id,
        "application_precision": sentinel.application_precision,
    }

    disbursement_custom_instruction = [SentinelCustomInstruction("disbursement_ci")]
    emi_custom_instruction = [SentinelCustomInstruction("emi_ci")]

    def test_activation_hook(
        self,
        mock_get_parameter: MagicMock,
        mock_disbursement_custom_instruction: MagicMock,
        mock_amortise: MagicMock,
        mock_create_aggregate_posting_instructions: MagicMock,
        mock_get_original_principal_custom_instructions: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock()
        mock_disbursement_custom_instruction.return_value = self.disbursement_custom_instruction
        mock_amortise.return_value = self.emi_custom_instruction
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.common_param_return_values
        )
        mock_create_aggregate_posting_instructions.return_value = [
            SentinelCustomInstruction("disbursement aggregate"),
            SentinelCustomInstruction("emi aggregate"),
        ]
        mock_get_original_principal_custom_instructions.return_value = [
            SentinelCustomInstruction("original principal")
        ]

        # construct expected result
        expected_custom_instructions = (
            self.disbursement_custom_instruction + self.emi_custom_instruction
        )
        expected = ActivationHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_custom_instructions,
                    client_batch_id=f"DRAWDOWN_LOAN_ACCOUNT_ACTIVATION_{DEFAULT_HOOK_EXECUTION_ID}",
                    value_datetime=DEFAULT_DATETIME,
                ),  # type: ignore
                PostingInstructionsDirective(
                    posting_instructions=[
                        SentinelCustomInstruction("disbursement aggregate"),
                        SentinelCustomInstruction("emi aggregate"),
                        SentinelCustomInstruction("original principal"),
                    ],
                    client_batch_id="AGGREGATE_LOC_DRAWDOWN_LOAN_ACCOUNT_ACTIVATION_"
                    + f"{DEFAULT_HOOK_EXECUTION_ID}",
                    value_datetime=DEFAULT_DATETIME,
                ),  # type: ignore
            ],
        )

        # run hook
        hook_args = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = drawdown_loan.activation_hook(vault=mock_vault, hook_arguments=hook_args)

        # validate result
        self.assertEqual(result, expected)

        mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    vault=mock_vault,
                    name=drawdown_loan.disbursement.PARAM_DEPOSIT_ACCOUNT,
                    at_datetime=None,
                ),
                call(
                    vault=mock_vault,
                    name=drawdown_loan.disbursement.PARAM_PRINCIPAL,
                    at_datetime=None,
                ),
                call(
                    vault=mock_vault,
                    name=drawdown_loan.common_parameters.PARAM_DENOMINATION,
                    at_datetime=None,
                ),
                call(vault=mock_vault, name=drawdown_loan.PARAM_LOC_ACCOUNT_ID),
            ]
        )

        mock_disbursement_custom_instruction.assert_called_once_with(
            account_id=ACCOUNT_ID,
            deposit_account_id=sentinel.deposit_account,
            principal=sentinel.principal,
            denomination=sentinel.denomination,
        )

        mock_amortise.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=drawdown_loan.declining_principal.AmortisationFeature,
            interest_calculation_feature=drawdown_loan.fixed_rate.interest_rate_interface,
        )

        mock_create_aggregate_posting_instructions.assert_called_once_with(
            aggregate_account_id=sentinel.loc_account_id,
            posting_instructions_by_supervisee={
                mock_vault.account_id: self.disbursement_custom_instruction
                + self.emi_custom_instruction
            },
            prefix="TOTAL",
            balances=BalanceDefaultDict(),
            addresses_to_aggregate=[
                drawdown_loan.lending_addresses.EMI,
                drawdown_loan.lending_addresses.PRINCIPAL,
            ],
            rounding_precision=sentinel.application_precision,
        )

        mock_get_original_principal_custom_instructions.assert_called_once_with(
            principal=sentinel.principal,
            loc_account_id=sentinel.loc_account_id,
            denomination=sentinel.denomination,
        )

    def test_activation_hook_when_disbursement_ci_is_none(
        self,
        mock_get_parameter: MagicMock,
        mock_disbursement_custom_instruction: MagicMock,
        mock_amortise: MagicMock,
        mock_create_aggregate_posting_instructions: MagicMock,
        mock_get_original_principal_custom_instructions: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock()
        mock_disbursement_custom_instruction.return_value = []
        mock_amortise.return_value = self.emi_custom_instruction
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.common_param_return_values
        )
        mock_create_aggregate_posting_instructions.return_value = [
            SentinelCustomInstruction("emi aggregate"),
        ]
        mock_get_original_principal_custom_instructions.return_value = [
            SentinelCustomInstruction("original principal")
        ]

        # construct expected result
        expected_custom_instructions = self.emi_custom_instruction
        expected = ActivationHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_custom_instructions,
                    client_batch_id=f"DRAWDOWN_LOAN_ACCOUNT_ACTIVATION_{DEFAULT_HOOK_EXECUTION_ID}",
                    value_datetime=DEFAULT_DATETIME,
                ),  # type: ignore
                PostingInstructionsDirective(
                    posting_instructions=[
                        SentinelCustomInstruction("emi aggregate"),
                        SentinelCustomInstruction("original principal"),
                    ],
                    client_batch_id="AGGREGATE_LOC_DRAWDOWN_LOAN_ACCOUNT_ACTIVATION_"
                    + f"{DEFAULT_HOOK_EXECUTION_ID}",
                    value_datetime=DEFAULT_DATETIME,
                ),  # type: ignore
            ],
        )

        # run hook
        hook_args = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = drawdown_loan.activation_hook(vault=mock_vault, hook_arguments=hook_args)

        # validate result
        self.assertEqual(result, expected)

        mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    vault=mock_vault,
                    name=drawdown_loan.disbursement.PARAM_DEPOSIT_ACCOUNT,
                    at_datetime=None,
                ),
                call(
                    vault=mock_vault,
                    name=drawdown_loan.disbursement.PARAM_PRINCIPAL,
                    at_datetime=None,
                ),
                call(
                    vault=mock_vault,
                    name=drawdown_loan.common_parameters.PARAM_DENOMINATION,
                    at_datetime=None,
                ),
                call(vault=mock_vault, name=drawdown_loan.PARAM_LOC_ACCOUNT_ID),
            ]
        )

        mock_disbursement_custom_instruction.assert_called_once_with(
            account_id=ACCOUNT_ID,
            deposit_account_id=sentinel.deposit_account,
            principal=sentinel.principal,
            denomination=sentinel.denomination,
        )

        mock_amortise.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=drawdown_loan.declining_principal.AmortisationFeature,
            interest_calculation_feature=drawdown_loan.fixed_rate.interest_rate_interface,
        )

        mock_create_aggregate_posting_instructions.assert_called_with(
            aggregate_account_id=sentinel.loc_account_id,
            posting_instructions_by_supervisee={mock_vault.account_id: self.emi_custom_instruction},
            prefix="TOTAL",
            balances=BalanceDefaultDict(),
            addresses_to_aggregate=[
                drawdown_loan.lending_addresses.EMI,
                drawdown_loan.lending_addresses.PRINCIPAL,
            ],
            rounding_precision=sentinel.application_precision,
        )

        mock_get_original_principal_custom_instructions.assert_called_once_with(
            principal=sentinel.principal,
            loc_account_id=sentinel.loc_account_id,
            denomination=sentinel.denomination,
        )

    def test_activation_hook_when_amortisation_ci_is_none(
        self,
        mock_get_parameter: MagicMock,
        mock_disbursement_custom_instruction: MagicMock,
        mock_amortise: MagicMock,
        mock_create_aggregate_posting_instructions: MagicMock,
        mock_get_original_principal_custom_instructions: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock()
        mock_disbursement_custom_instruction.return_value = self.disbursement_custom_instruction
        mock_amortise.return_value = []
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.common_param_return_values
        )
        mock_create_aggregate_posting_instructions.return_value = [
            SentinelCustomInstruction("disbursement aggregate"),
        ]
        mock_get_original_principal_custom_instructions.return_value = [
            SentinelCustomInstruction("original principal")
        ]

        # construct expected result
        expected_custom_instructions = self.disbursement_custom_instruction
        expected = ActivationHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_custom_instructions,
                    client_batch_id=f"DRAWDOWN_LOAN_ACCOUNT_ACTIVATION_{DEFAULT_HOOK_EXECUTION_ID}",
                    value_datetime=DEFAULT_DATETIME,
                ),  # type: ignore
                PostingInstructionsDirective(
                    posting_instructions=[
                        SentinelCustomInstruction("disbursement aggregate"),
                        SentinelCustomInstruction("original principal"),
                    ],
                    client_batch_id="AGGREGATE_LOC_DRAWDOWN_LOAN_ACCOUNT_ACTIVATION_"
                    + f"{DEFAULT_HOOK_EXECUTION_ID}",
                    value_datetime=DEFAULT_DATETIME,
                ),  # type: ignore
            ],
        )

        # run hook
        hook_args = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = drawdown_loan.activation_hook(vault=mock_vault, hook_arguments=hook_args)

        # validate result
        self.assertEqual(result, expected)

        mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    vault=mock_vault,
                    name=drawdown_loan.disbursement.PARAM_DEPOSIT_ACCOUNT,
                    at_datetime=None,
                ),
                call(
                    vault=mock_vault,
                    name=drawdown_loan.disbursement.PARAM_PRINCIPAL,
                    at_datetime=None,
                ),
                call(
                    vault=mock_vault,
                    name=drawdown_loan.common_parameters.PARAM_DENOMINATION,
                    at_datetime=None,
                ),
                call(
                    vault=mock_vault,
                    name=drawdown_loan.PARAM_LOC_ACCOUNT_ID,
                ),
            ]
        )

        mock_disbursement_custom_instruction.assert_called_once_with(
            account_id=ACCOUNT_ID,
            deposit_account_id=sentinel.deposit_account,
            principal=sentinel.principal,
            denomination=sentinel.denomination,
        )

        mock_amortise.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=drawdown_loan.declining_principal.AmortisationFeature,
            interest_calculation_feature=drawdown_loan.fixed_rate.interest_rate_interface,
        )

        mock_create_aggregate_posting_instructions.assert_called_with(
            aggregate_account_id=sentinel.loc_account_id,
            posting_instructions_by_supervisee={
                mock_vault.account_id: self.disbursement_custom_instruction
            },
            prefix="TOTAL",
            balances=BalanceDefaultDict(),
            addresses_to_aggregate=[
                drawdown_loan.lending_addresses.EMI,
                drawdown_loan.lending_addresses.PRINCIPAL,
            ],
            rounding_precision=sentinel.application_precision,
        )

        mock_get_original_principal_custom_instructions.assert_called_once_with(
            principal=sentinel.principal,
            loc_account_id=sentinel.loc_account_id,
            denomination=sentinel.denomination,
        )

    def test_activation_hook_when_disbursement_and_amortisation_cis_are_none(
        self,
        mock_get_parameter: MagicMock,
        mock_disbursement_custom_instruction: MagicMock,
        mock_amortise: MagicMock,
        mock_create_aggregate_posting_instructions: MagicMock,
        mock_get_original_principal_custom_instructions: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock()
        mock_disbursement_custom_instruction.return_value = []
        mock_amortise.return_value = []
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.common_param_return_values
        )

        # construct expected result
        expected = ActivationHookResult(
            posting_instructions_directives=[],
        )

        # run hook
        hook_args = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = drawdown_loan.activation_hook(vault=mock_vault, hook_arguments=hook_args)

        # validate result
        self.assertEqual(result, expected)

        mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    vault=mock_vault,
                    name=drawdown_loan.disbursement.PARAM_DEPOSIT_ACCOUNT,
                    at_datetime=None,
                ),
                call(
                    vault=mock_vault,
                    name=drawdown_loan.disbursement.PARAM_PRINCIPAL,
                    at_datetime=None,
                ),
                call(
                    vault=mock_vault,
                    name=drawdown_loan.common_parameters.PARAM_DENOMINATION,
                    at_datetime=None,
                ),
            ]
        )

        mock_disbursement_custom_instruction.assert_called_once_with(
            account_id=ACCOUNT_ID,
            deposit_account_id=sentinel.deposit_account,
            principal=sentinel.principal,
            denomination=sentinel.denomination,
        )

        mock_amortise.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=drawdown_loan.declining_principal.AmortisationFeature,
            interest_calculation_feature=drawdown_loan.fixed_rate.interest_rate_interface,
        )

        mock_create_aggregate_posting_instructions.assert_not_called()

        mock_get_original_principal_custom_instructions.assert_not_called()
