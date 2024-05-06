# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel
from zoneinfo import ZoneInfo

# library
import library.line_of_credit.supervisors.template.line_of_credit_supervisor as line_of_credit_supervisor  # noqa: E501
from library.line_of_credit.test.unit.test_line_of_credit_supervisor_common import (
    LineOfCreditSupervisorTestBase,
)

# features
from library.features.v4.common.test.mocks import (
    mock_supervisor_get_supervisees_for_alias,
    mock_utils_get_parameter,
)

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    BalanceDefaultDict,
    CustomInstruction,
    Phase,
    SupervisorPostPostingHookArguments,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    AccountNotificationDirective,
    BalanceCoordinate,
    CustomInstruction as _CustomInstruction,
    PostingInstructionsDirective,
    SupervisorScheduledEventHookArguments,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    DEFAULT_POSTINGS,
    SentinelAccountNotificationDirective,
    SentinelCustomInstruction,
    SentinelPosting,
)
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import (
    SuperviseeContractVault,
)

DEFAULT_COORDINATE = BalanceCoordinate(
    DEFAULT_ADDRESS, DEFAULT_ASSET, sentinel.denomination, Phase.COMMITTED
)
DEFAULT_DATETIME = datetime(2023, 1, 1, tzinfo=ZoneInfo("UTC"))


class GetLoanVaultsForRepaymentDistributionTest(LineOfCreditSupervisorTestBase):
    loan_1_vault = LineOfCreditSupervisorTestBase().create_supervisee_mock(account_id="loan_1")
    loan_2_vault = LineOfCreditSupervisorTestBase().create_supervisee_mock(account_id="loan_2")

    loan_vaults = [loan_1_vault, loan_2_vault]

    def test_only_1_loan_supervisee_returned_when_providing_target_account_id(self):
        result = line_of_credit_supervisor._get_loan_vaults_for_repayment_distribution(
            loan_vaults=self.loan_vaults,  # type: ignore
            posting_instruction=self.inbound_hard_settlement(
                amount=Decimal("10"), instruction_details={"target_account_id": "loan_1"}
            ),
        )

        self.assertListEqual(result, [self.loan_1_vault])

    def test_all_loan_supervisees_returned_when_no_target_account_id_provided(self):
        result = line_of_credit_supervisor._get_loan_vaults_for_repayment_distribution(
            loan_vaults=self.loan_vaults,  # type: ignore
            posting_instruction=self.inbound_hard_settlement(amount=Decimal("10")),
        )

        self.assertListEqual(result, self.loan_vaults)

    def test_empty_list_is_returned_when_providing_an_invalid_target_account_id(self):
        result = line_of_credit_supervisor._get_loan_vaults_for_repayment_distribution(
            loan_vaults=self.loan_vaults,  # type: ignore
            posting_instruction=self.inbound_hard_settlement(
                amount=Decimal("10"),
                instruction_details={"target_account_id": "invalid_account_id"},
            ),
        )

        self.assertListEqual(result, [])


@patch.object(line_of_credit_supervisor.overpayment, "validate_overpayment_across_supervisees")
class ValidateRepaymentTest(LineOfCreditSupervisorTestBase):
    def test_returns_rejection_when_overpayment_rejection_exists(
        self,
        mock_validate_overpayment_across_supervisees: MagicMock,
    ):
        mock_validate_overpayment_across_supervisees.return_value = sentinel.overpayment_rejection

        result = line_of_credit_supervisor._validate_repayment(
            loc_vault=sentinel.loc_vault,
            all_supervisee_balances=[sentinel.all_supervisee_balances],
            repayment_amount=sentinel.repayment_amount,
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, sentinel.overpayment_rejection)

        mock_validate_overpayment_across_supervisees.assert_called_once_with(
            main_vault=sentinel.loc_vault,
            all_supervisee_balances=[sentinel.all_supervisee_balances],
            repayment_amount=sentinel.repayment_amount,
            denomination=sentinel.denomination,
            rounding_precision=2,
        )

    def test_none_when_no_overpayment_rejection_is_present(
        self,
        mock_validate_overpayment_across_supervisees: MagicMock,
    ):
        mock_validate_overpayment_across_supervisees.return_value = None

        result = line_of_credit_supervisor._validate_repayment(
            loc_vault=sentinel.loc_vault,
            all_supervisee_balances=[sentinel.all_supervisee_balances],
            repayment_amount=sentinel.repayment_amount,
            denomination=sentinel.denomination,
            rounding_precision=sentinel.rounding_precision,
        )

        self.assertIsNone(result)

        mock_validate_overpayment_across_supervisees.assert_called_once_with(
            main_vault=sentinel.loc_vault,
            all_supervisee_balances=[sentinel.all_supervisee_balances],
            repayment_amount=sentinel.repayment_amount,
            denomination=sentinel.denomination,
            rounding_precision=sentinel.rounding_precision,
        )


@patch.object(
    line_of_credit_supervisor.supervisor_utils, "get_balances_default_dicts_from_timeseries"
)
@patch.object(
    line_of_credit_supervisor.payments, "generate_repayment_postings_for_multiple_targets"
)
@patch.object(line_of_credit_supervisor, "_aggregate_repayment_postings")
@patch.object(line_of_credit_supervisor, "_get_loans_closure_notification_directives")
@patch.object(line_of_credit_supervisor, "_handle_overpayment")
class HandleRepaymentTest(LineOfCreditSupervisorTestBase):
    def test_correct_posting_instructions_directive_dict_returned(
        self,
        mock_handle_overpayment: MagicMock,
        mock_get_loans_closure_notification_directives: MagicMock,
        mock_aggregate_repayment_postings: MagicMock,
        mock_generate_repayment_postings_for_multiple_targets: MagicMock,
        mock_get_balances_default_dicts_from_timeseries: MagicMock,
    ):
        mock_loan_1 = self.create_supervisee_mock(account_id="loan_1")
        mock_loan_2 = self.create_supervisee_mock(account_id="loan_2")
        mock_loc = self.create_supervisee_mock(account_id="loc")

        balances_per_target = {
            mock_loc.account_id: sentinel.loc_balances,
            mock_loan_1.account_id: sentinel.loan_1_balances,
            mock_loan_2.account_id: sentinel.loan_2_balances,
        }
        mock_get_balances_default_dicts_from_timeseries.return_value = balances_per_target
        repayment_instructions_per_target = {
            mock_loc.account_id: [SentinelCustomInstruction("loc_instruction")],
            mock_loan_1.account_id: [SentinelCustomInstruction("loan_1_instruction")],
            mock_loan_2.account_id: [],
        }
        mock_generate_repayment_postings_for_multiple_targets.return_value = (
            repayment_instructions_per_target
        )
        mock_aggregate_repayment_postings.return_value = [
            SentinelCustomInstruction("aggregated_repayments_custom_instructions")
        ]
        mock_get_loans_closure_notification_directives.return_value = {
            mock_loc.account_id: [SentinelAccountNotificationDirective("closures_notification")]
        }

        expected_loan_1_posting_instruction_directives = [
            PostingInstructionsDirective(
                posting_instructions=[SentinelCustomInstruction("loan_1_instruction")],
                client_batch_id="REPAYMENT_"
                + f"{mock_loan_1.account_id}_{mock_loan_1.get_hook_execution_id()}",
                value_datetime=DEFAULT_DATETIME,
            )
        ]
        expected_loan_2_posting_instruction_directives = []
        expected_loc_posting_instruction_directive = [
            PostingInstructionsDirective(
                posting_instructions=[
                    SentinelCustomInstruction("loc_instruction"),
                    SentinelCustomInstruction("aggregated_repayments_custom_instructions"),
                ],
                client_batch_id="REPAYMENT_"
                + f"{mock_loc.account_id}_{mock_loc.get_hook_execution_id()}",
                value_datetime=DEFAULT_DATETIME,
            ),
        ]

        expected_posting_directives = {
            mock_loc.account_id: expected_loc_posting_instruction_directive,
            mock_loan_1.account_id: expected_loan_1_posting_instruction_directives,
            mock_loan_2.account_id: expected_loan_2_posting_instruction_directives,
        }
        expected_notification_directives = {
            mock_loc.account_id: [SentinelAccountNotificationDirective("closures_notification")]
        }
        expected_result: tuple[
            dict[str, list[PostingInstructionsDirective]],
            dict[str, list[AccountNotificationDirective]],
        ] = (expected_posting_directives, expected_notification_directives)

        hook_arguments = SupervisorPostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            supervisee_posting_instructions={
                mock_loc.account_id: [
                    self.inbound_hard_settlement(
                        amount=Decimal("100"), denomination=sentinel.denomination
                    )
                ]
            },
            supervisee_client_transactions={},
        )
        result = line_of_credit_supervisor._handle_repayment(
            hook_arguments=hook_arguments,
            sorted_repayment_targets=[mock_loc, mock_loan_1, mock_loan_2],
            loc_vault=mock_loc,
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, expected_result)

        mock_get_balances_default_dicts_from_timeseries.assert_called_once_with(
            supervisees=[mock_loc, mock_loan_1, mock_loan_2], effective_datetime=DEFAULT_DATETIME
        )
        mock_generate_repayment_postings_for_multiple_targets.assert_called_once_with(
            main_vault=mock_loc,
            sorted_repayment_targets=[mock_loc, mock_loan_1, mock_loan_2],
            hook_arguments=hook_arguments,
            repayment_hierarchy=[
                [address]
                for address in line_of_credit_supervisor.lending_addresses.REPAYMENT_HIERARCHY
            ],
            overpayment_features=[
                line_of_credit_supervisor.lending_interfaces.MultiTargetOverpayment(
                    handle_overpayment=mock_handle_overpayment
                )
            ],
        )
        mock_aggregate_repayment_postings.assert_called_once_with(
            repayments_custom_instructions_per_target=repayment_instructions_per_target,
            loc_vault=mock_loc,
            loc_balances=balances_per_target[mock_loc.account_id],
        )
        mock_get_loans_closure_notification_directives.assert_called_once_with(
            loc_vault=mock_loc,
            repayments_custom_instructions_per_target=repayment_instructions_per_target,
            balances_per_target=balances_per_target,
            denomination=sentinel.denomination,
        )


class HandleOverpaymentTest(LineOfCreditSupervisorTestBase):
    def setUp(self) -> None:
        self.mock_get_overpayment_fee_rate_parameter = patch.object(
            line_of_credit_supervisor.overpayment, "get_overpayment_fee_rate_parameter"
        ).start()
        self.mock_get_overpayment_fee = patch.object(
            line_of_credit_supervisor.overpayment, "get_overpayment_fee"
        ).start()
        self.mock_get_max_overpayment_fee = patch.object(
            line_of_credit_supervisor.overpayment, "get_max_overpayment_fee"
        ).start()
        self.mock_get_overpayment_fee_postings = patch.object(
            line_of_credit_supervisor.overpayment, "get_overpayment_fee_postings"
        ).start()
        self.mock_get_overpayment_fee_income_account_parameter = patch.object(
            line_of_credit_supervisor.overpayment, "get_overpayment_fee_income_account_parameter"
        ).start()
        self.mock_distribute_overpayment = patch.object(
            line_of_credit_supervisor, "_distribute_overpayment"
        ).start()

        self.main_vault = self.create_supervisee_mock(account_id="main_vault")
        self.loan_1 = self.create_supervisee_mock(account_id="loan_1")
        self.loan_2 = self.create_supervisee_mock(account_id="loan_2")
        self.overpayment_amount = Decimal("100")

        main_vault_balances = BalanceDefaultDict(
            mapping={DEFAULT_COORDINATE: self.balance(net=Decimal("20"))}
        )
        self.loan_1_balances = BalanceDefaultDict(
            mapping={DEFAULT_COORDINATE: self.balance(net=Decimal("10"))}
        )
        self.loan_2_balances = BalanceDefaultDict(
            mapping={DEFAULT_COORDINATE: self.balance(net=Decimal("5"))}
        )

        self.balances_per_target_vault: dict[SuperviseeContractVault, BalanceDefaultDict] = {
            self.main_vault: main_vault_balances,
            self.loan_1: self.loan_1_balances,
            self.loan_2: self.loan_2_balances,
        }

        self.mock_get_overpayment_fee_rate_parameter.return_value = sentinel.overpayment_fee_rate
        self.mock_get_overpayment_fee.return_value = Decimal("10")
        self.mock_get_max_overpayment_fee.return_value = Decimal("20")
        self.mock_get_overpayment_fee_postings.return_value = [SentinelPosting("overpayment_fee")]
        self.mock_get_overpayment_fee_income_account_parameter.return_value = (
            sentinel.overpayment_fee_income_account
        )
        self.mock_distribute_overpayment.return_value = {
            self.loan_1.account_id: [SentinelPosting("loan_1_overpayment")],
            self.loan_2.account_id: [SentinelPosting("loan_2_overpayment")],
        }

        self.merged_balances = BalanceDefaultDict(
            mapping={DEFAULT_COORDINATE: self.balance(net=Decimal("35"))}
        )

        self.addCleanup(patch.stopall)

        return super().setUp()

    def test_overpayment_fee_exceeds_max(self):
        self.mock_get_overpayment_fee.return_value = Decimal("10")
        self.mock_get_max_overpayment_fee.return_value = Decimal("5")

        overpayment_excluding_fee = self.overpayment_amount - Decimal("5")

        excepted_result = {
            self.main_vault.account_id: [SentinelPosting("overpayment_fee")],
            self.loan_1.account_id: [SentinelPosting("loan_1_overpayment")],
            self.loan_2.account_id: [SentinelPosting("loan_2_overpayment")],
        }

        result = line_of_credit_supervisor._handle_overpayment(
            main_vault=self.main_vault,
            overpayment_amount=self.overpayment_amount,
            denomination=self.default_denomination,
            balances_per_target_vault=self.balances_per_target_vault,
        )

        self.assertDictEqual(result, excepted_result)

        self.mock_get_overpayment_fee_rate_parameter.assert_called_once_with(vault=self.main_vault)
        self.mock_get_overpayment_fee.assert_called_once_with(
            principal_repaid=self.overpayment_amount,
            overpayment_fee_rate=sentinel.overpayment_fee_rate,
            precision=2,
        )
        self.mock_get_max_overpayment_fee.assert_called_once_with(
            fee_rate=sentinel.overpayment_fee_rate,
            balances=self.merged_balances,
            denomination=self.default_denomination,
            precision=2,
        )
        self.mock_get_overpayment_fee_income_account_parameter.assert_called_once_with(
            vault=self.main_vault
        )
        self.mock_get_overpayment_fee_postings.assert_called_once_with(
            overpayment_fee=Decimal("5"),
            denomination=self.default_denomination,
            customer_account_id=self.main_vault.account_id,
            customer_account_address=DEFAULT_ADDRESS,
            internal_account=sentinel.overpayment_fee_income_account,
        )

        balances_per_loan_vault = {
            self.loan_1: self.loan_1_balances,
            self.loan_2: self.loan_2_balances,
        }
        self.mock_distribute_overpayment.assert_called_once_with(
            overpayment_amount=overpayment_excluding_fee,
            denomination=self.default_denomination,
            balances_per_loan_vault=balances_per_loan_vault,
        )

    def test_overpayment_fee_does_not_exceed_max(self):
        self.mock_get_overpayment_fee.return_value = Decimal("8")
        self.mock_get_max_overpayment_fee.return_value = Decimal("10")

        overpayment_excluding_fee = self.overpayment_amount - Decimal("8")

        excepted_result = {
            self.main_vault.account_id: [SentinelPosting("overpayment_fee")],
            self.loan_1.account_id: [SentinelPosting("loan_1_overpayment")],
            self.loan_2.account_id: [SentinelPosting("loan_2_overpayment")],
        }

        result = line_of_credit_supervisor._handle_overpayment(
            main_vault=self.main_vault,
            overpayment_amount=self.overpayment_amount,
            denomination=self.default_denomination,
            balances_per_target_vault=self.balances_per_target_vault,
        )

        self.assertDictEqual(result, excepted_result)

        self.mock_get_overpayment_fee_rate_parameter.assert_called_once_with(vault=self.main_vault)
        self.mock_get_overpayment_fee.assert_called_once_with(
            principal_repaid=self.overpayment_amount,
            overpayment_fee_rate=sentinel.overpayment_fee_rate,
            precision=2,
        )
        self.mock_get_max_overpayment_fee.assert_called_once_with(
            fee_rate=sentinel.overpayment_fee_rate,
            balances=self.merged_balances,
            denomination=self.default_denomination,
            precision=2,
        )
        self.mock_get_overpayment_fee_income_account_parameter.assert_called_once_with(
            vault=self.main_vault
        )
        self.mock_get_overpayment_fee_postings.assert_called_once_with(
            overpayment_fee=Decimal("8"),
            denomination=self.default_denomination,
            customer_account_id=self.main_vault.account_id,
            customer_account_address=DEFAULT_ADDRESS,
            internal_account=sentinel.overpayment_fee_income_account,
        )

        balances_per_loan_vault = {
            self.loan_1: self.loan_1_balances,
            self.loan_2: self.loan_2_balances,
        }
        self.mock_distribute_overpayment.assert_called_once_with(
            overpayment_amount=overpayment_excluding_fee,
            denomination=self.default_denomination,
            balances_per_loan_vault=balances_per_loan_vault,
        )


@patch.object(line_of_credit_supervisor.payments, "distribute_repayment_for_multiple_targets")
@patch.object(line_of_credit_supervisor.payments, "redistribute_postings")
@patch.object(line_of_credit_supervisor.utils, "create_postings")
@patch.object(line_of_credit_supervisor.interest_application_supervisor, "repay_accrued_interest")
class DistributeOverpaymentTest(LineOfCreditSupervisorTestBase):
    def test_overpayment_distributed_correctly(
        self,
        mock_repay_accrued_interest: MagicMock,
        mock_create_postings: MagicMock,
        mock_redistribute_postings: MagicMock,
        mock_distribute_repayment_for_multiple_targets: MagicMock,
    ):
        PRINCIPAL = line_of_credit_supervisor.lending_addresses.PRINCIPAL
        ACCRUED_INTEREST = line_of_credit_supervisor.lending_addresses.ACCRUED_INTEREST_RECEIVABLE
        NON_EMI_ACCRUED_INTEREST = (
            line_of_credit_supervisor.lending_addresses.NON_EMI_ACCRUED_INTEREST_RECEIVABLE
        )

        mock_loan_1 = self.create_supervisee_mock(account_id="loan_1")
        mock_loan_2 = self.create_supervisee_mock(account_id="loan_2")
        overpayment_per_target = {
            mock_loan_1.account_id: {
                PRINCIPAL: line_of_credit_supervisor.payments.RepaymentAmounts(
                    unrounded_amount=Decimal("10.00001"), rounded_amount=Decimal("10")
                ),
                ACCRUED_INTEREST: line_of_credit_supervisor.payments.RepaymentAmounts(
                    unrounded_amount=Decimal("0.0002"), rounded_amount=Decimal("0")
                ),
                NON_EMI_ACCRUED_INTEREST: line_of_credit_supervisor.payments.RepaymentAmounts(
                    unrounded_amount=Decimal("0.081"), rounded_amount=Decimal("0.08")
                ),
            },
            mock_loan_2.account_id: {
                PRINCIPAL: line_of_credit_supervisor.payments.RepaymentAmounts(
                    unrounded_amount=Decimal("20.00001"), rounded_amount=Decimal("20")
                ),
                ACCRUED_INTEREST: line_of_credit_supervisor.payments.RepaymentAmounts(
                    unrounded_amount=Decimal("5.00001"), rounded_amount=Decimal("5")
                ),
                NON_EMI_ACCRUED_INTEREST: line_of_credit_supervisor.payments.RepaymentAmounts(
                    unrounded_amount=Decimal("0"), rounded_amount=Decimal("0")
                ),
            },
        }
        mock_distribute_repayment_for_multiple_targets.return_value = (
            overpayment_per_target,
            sentinel.remaining_amount,
        )

        mock_redistribute_postings.side_effect = [
            [sentinel.loan_1_principal_postings],
            [sentinel.loan_2_principal_postings],
        ]

        mock_create_postings.side_effect = [
            [sentinel.overpayment_tracker_1],
            [sentinel.overpayment_since_prev_due_amount_calc_1],
            [sentinel.overpayment_tracker_2],
            [sentinel.overpayment_since_prev_due_amount_calc_2],
        ]

        mock_repay_accrued_interest.side_effect = [
            [sentinel.loan_1_accrued_interest_postings],
            [sentinel.loan_2_accrued_interest_postings],
        ]

        expected_result = {
            mock_loan_1.account_id: [
                sentinel.loan_1_principal_postings,
                sentinel.overpayment_tracker_1,
                sentinel.overpayment_since_prev_due_amount_calc_1,
                sentinel.loan_1_accrued_interest_postings,
            ],
            mock_loan_2.account_id: [
                sentinel.loan_2_principal_postings,
                sentinel.overpayment_tracker_2,
                sentinel.overpayment_since_prev_due_amount_calc_2,
                sentinel.loan_2_accrued_interest_postings,
            ],
        }

        balances_per_loan_vault: dict[SuperviseeContractVault, BalanceDefaultDict] = {
            mock_loan_1: sentinel.loan_1_balances,
            mock_loan_2: sentinel.loan_2_balances,
        }
        result = line_of_credit_supervisor._distribute_overpayment(
            overpayment_amount=sentinel.overpayment_amount,
            denomination=self.default_denomination,
            balances_per_loan_vault=balances_per_loan_vault,
        )

        self.assertDictEqual(result, expected_result)

        mock_distribute_repayment_for_multiple_targets.assert_called_once_with(
            balances_per_target={
                mock_loan_1.account_id: sentinel.loan_1_balances,
                mock_loan_2.account_id: sentinel.loan_2_balances,
            },
            repayment_amount=sentinel.overpayment_amount,
            denomination=self.default_denomination,
            repayment_hierarchy=line_of_credit_supervisor.lending_addresses.OVERPAYMENT_HIERARCHY_SUPERVISOR,  # noqa: E501
        )

        mock_redistribute_postings.assert_has_calls(
            calls=[
                call(
                    debit_account=mock_loan_1.account_id,
                    amount=Decimal("10"),
                    denomination=self.default_denomination,
                    credit_account=mock_loan_1.account_id,
                    credit_address=PRINCIPAL,
                    debit_address=line_of_credit_supervisor.lending_addresses.INTERNAL_CONTRA,
                ),
                call(
                    debit_account=mock_loan_2.account_id,
                    amount=Decimal("20"),
                    denomination=self.default_denomination,
                    credit_account=mock_loan_2.account_id,
                    credit_address=PRINCIPAL,
                    debit_address=line_of_credit_supervisor.lending_addresses.INTERNAL_CONTRA,
                ),
            ]
        )

        mock_create_postings.assert_has_calls(
            calls=[
                call(
                    amount=Decimal("10"),
                    debit_account=mock_loan_1.account_id,
                    debit_address=line_of_credit_supervisor.overpayment.OVERPAYMENT,
                    credit_account=mock_loan_1.account_id,
                    credit_address=line_of_credit_supervisor.lending_addresses.INTERNAL_CONTRA,
                    denomination=self.default_denomination,
                ),
                call(
                    amount=Decimal("10"),
                    debit_account=mock_loan_1.account_id,
                    debit_address=(
                        line_of_credit_supervisor.overpayment.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER  # noqa: E501
                    ),
                    credit_account=mock_loan_1.account_id,
                    credit_address=line_of_credit_supervisor.lending_addresses.INTERNAL_CONTRA,
                    denomination=self.default_denomination,
                ),
                call(
                    amount=Decimal("20"),
                    debit_account=mock_loan_2.account_id,
                    debit_address=line_of_credit_supervisor.overpayment.OVERPAYMENT,
                    credit_account=mock_loan_2.account_id,
                    credit_address=line_of_credit_supervisor.lending_addresses.INTERNAL_CONTRA,
                    denomination=self.default_denomination,
                ),
                call(
                    amount=Decimal("20"),
                    debit_account=mock_loan_2.account_id,
                    debit_address=(
                        line_of_credit_supervisor.overpayment.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER  # noqa: E501
                    ),
                    credit_account=mock_loan_2.account_id,
                    credit_address=line_of_credit_supervisor.lending_addresses.INTERNAL_CONTRA,
                    denomination=self.default_denomination,
                ),
            ]
        )

        mock_repay_accrued_interest.assert_has_calls(
            calls=[
                call(
                    vault=mock_loan_1,
                    repayment_amount=Decimal("0.0812"),
                    denomination=self.default_denomination,
                    balances=sentinel.loan_1_balances,
                    application_customer_address=(
                        line_of_credit_supervisor.lending_addresses.INTERNAL_CONTRA
                    ),
                ),
                call(
                    vault=mock_loan_2,
                    repayment_amount=Decimal("5.00001"),
                    denomination=self.default_denomination,
                    balances=sentinel.loan_2_balances,
                    application_customer_address=(
                        line_of_credit_supervisor.lending_addresses.INTERNAL_CONTRA
                    ),
                ),
            ]
        )


@patch.object(line_of_credit_supervisor.supervisor_utils, "create_aggregate_posting_instructions")
class AggregateRepaymentPostings(LineOfCreditSupervisorTestBase):
    def setUp(self) -> None:
        self.mock_loan_1 = self.create_supervisee_mock(
            supervisee_alias=line_of_credit_supervisor.DRAWDOWN_LOAN_ALIAS, account_id="loan_1"
        )
        self.mock_loan_2 = self.create_supervisee_mock(
            supervisee_alias=line_of_credit_supervisor.DRAWDOWN_LOAN_ALIAS, account_id="loan_2"
        )
        self.mock_loc = self.create_supervisee_mock(
            supervisee_alias=line_of_credit_supervisor.LOC_ALIAS, account_id="loc"
        )

        self.repayments_custom_instructions_per_target: dict[str, list[CustomInstruction]] = {
            self.mock_loan_1.account_id: sentinel.loan_1_custom_instructions,
            self.mock_loan_2.account_id: sentinel.loan_2_custom_instructions,
            self.mock_loc.account_id: sentinel.loc_custom_instructions,
        }

        return super().setUp()

    def test_correct_posting_instructions_directive_returned(
        self, mock_create_aggregate_posting_instructions: MagicMock
    ):
        custom_instructions_list: list[CustomInstruction] = [
            SentinelCustomInstruction("aggregate_posting_instructions"),
        ]
        mock_create_aggregate_posting_instructions.return_value = custom_instructions_list

        expected_result = custom_instructions_list

        result = line_of_credit_supervisor._aggregate_repayment_postings(
            repayments_custom_instructions_per_target=(
                self.repayments_custom_instructions_per_target
            ),
            loc_vault=self.mock_loc,
            loc_balances=sentinel.loc_balances,
        )

        self.assertEqual(result, expected_result)

        flat_overpayment_hierarchy = [
            address
            for address_list in (
                line_of_credit_supervisor.lending_addresses.OVERPAYMENT_HIERARCHY_SUPERVISOR
            )
            for address in address_list
        ]
        mock_create_aggregate_posting_instructions.assert_called_once_with(
            aggregate_account_id=self.mock_loc.account_id,
            posting_instructions_by_supervisee={
                self.mock_loan_1.account_id: sentinel.loan_1_custom_instructions,
                self.mock_loan_2.account_id: sentinel.loan_2_custom_instructions,
            },
            prefix="TOTAL",
            balances=sentinel.loc_balances,
            addresses_to_aggregate=[
                *line_of_credit_supervisor.lending_addresses.REPAYMENT_HIERARCHY,
                *flat_overpayment_hierarchy,
            ],
            force_override=False,
        )

    def test_no_aggregate_posting_instructions(
        self, mock_create_aggregate_posting_instructions: MagicMock
    ):
        mock_create_aggregate_posting_instructions.return_value = []

        expected_result = []

        result = line_of_credit_supervisor._aggregate_repayment_postings(
            repayments_custom_instructions_per_target=(
                self.repayments_custom_instructions_per_target
            ),
            loc_vault=self.mock_loc,
            loc_balances=sentinel.loc_balances,
        )

        self.assertEqual(result, expected_result)

        flat_overpayment_hierarchy = [
            address
            for address_list in (
                line_of_credit_supervisor.lending_addresses.OVERPAYMENT_HIERARCHY_SUPERVISOR
            )
            for address in address_list
        ]
        mock_create_aggregate_posting_instructions.assert_called_once_with(
            aggregate_account_id=self.mock_loc.account_id,
            posting_instructions_by_supervisee={
                self.mock_loan_1.account_id: sentinel.loan_1_custom_instructions,
                self.mock_loan_2.account_id: sentinel.loan_2_custom_instructions,
            },
            prefix="TOTAL",
            balances=sentinel.loc_balances,
            addresses_to_aggregate=[
                *line_of_credit_supervisor.lending_addresses.REPAYMENT_HIERARCHY,
                *flat_overpayment_hierarchy,
            ],
            force_override=False,
        )


@patch.object(line_of_credit_supervisor, "_get_paid_off_loans_notification")
class GetLoansClosureNotificationDirectivesTest(LineOfCreditSupervisorTestBase):
    def test_correct_notification_directive_returned(
        self, mock_get_paid_off_loans_notification: MagicMock
    ):
        mock_loan_1 = self.create_supervisee_mock(account_id="loan_1")
        mock_loan_2 = self.create_supervisee_mock(account_id="loan_2")
        mock_loc = self.create_supervisee_mock(account_id="loc")
        mock_get_paid_off_loans_notification.return_value = [
            SentinelAccountNotificationDirective("closure_notification")
        ]

        expected_result = {
            mock_loc.account_id: [SentinelAccountNotificationDirective("closure_notification")]
        }

        repayments_custom_instructions_per_target: dict[str, list[CustomInstruction]] = {
            mock_loc.account_id: [SentinelCustomInstruction("loc_instructions")],
            mock_loan_1.account_id: [SentinelCustomInstruction("loan_1_instructions")],
            mock_loan_2.account_id: [SentinelCustomInstruction("loan_2_instructions")],
        }
        balances_per_target = sentinel.balances_per_target
        result = line_of_credit_supervisor._get_loans_closure_notification_directives(
            loc_vault=mock_loc,
            repayments_custom_instructions_per_target=repayments_custom_instructions_per_target,
            balances_per_target=balances_per_target,
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, expected_result)

        repayments_custom_instructions_per_loan: dict[str, list[CustomInstruction]] = {
            mock_loan_1.account_id: [SentinelCustomInstruction("loan_1_instructions")],
            mock_loan_2.account_id: [SentinelCustomInstruction("loan_2_instructions")],
        }
        mock_get_paid_off_loans_notification.assert_called_once_with(
            repayment_custom_instructions_per_loan=repayments_custom_instructions_per_loan,
            balances_per_target=balances_per_target,
            denomination=sentinel.denomination,
        )


@patch.object(line_of_credit_supervisor, "_get_loc_vault")
@patch.object(line_of_credit_supervisor.supervisor_utils, "get_supervisees_for_alias")
class GetLocAndLoanSuperviseesTest(LineOfCreditSupervisorTestBase):
    def test_all_supervisees_are_returned(
        self, mock_get_supervisees_for_alias: MagicMock, mock_get_loc_vault: MagicMock
    ):
        mock_get_loc_vault.return_value = sentinel.dummy1
        mock_get_supervisees_for_alias.side_effect = mock_supervisor_get_supervisees_for_alias(
            supervisees={
                line_of_credit_supervisor.LOC_ALIAS: [sentinel.dummy1],
                line_of_credit_supervisor.DRAWDOWN_LOAN_ALIAS: [sentinel.dummy2, sentinel.dummy3],
            }
        )

        expected = sentinel.dummy1, [sentinel.dummy2, sentinel.dummy3]

        result = line_of_credit_supervisor._get_loc_and_loan_supervisee_vault_objects(
            sentinel.supervisor
        )
        self.assertEqual(result, expected)
        mock_get_loc_vault.assert_called_once_with(vault=sentinel.supervisor)
        mock_get_supervisees_for_alias.assert_called_once_with(
            vault=sentinel.supervisor, alias=line_of_credit_supervisor.DRAWDOWN_LOAN_ALIAS
        )


@patch.object(line_of_credit_supervisor.supervisor_utils, "get_supervisees_for_alias")
class GetLocVaultTest(LineOfCreditSupervisorTestBase):
    def test_get_loc_vault_returns_loc_vault(self, mock_get_supervisees_for_alias: MagicMock):
        mock_get_supervisees_for_alias.side_effect = mock_supervisor_get_supervisees_for_alias(
            supervisees={
                line_of_credit_supervisor.LOC_ALIAS: [sentinel.loc_vault],
                line_of_credit_supervisor.DRAWDOWN_LOAN_ALIAS: [sentinel.dummy2, sentinel.dummy3],
            }
        )

        expected = sentinel.loc_vault

        result = line_of_credit_supervisor._get_loc_vault(sentinel.supervisor)
        self.assertEqual(result, expected)
        mock_get_supervisees_for_alias.assert_called_once_with(
            vault=sentinel.supervisor, alias=line_of_credit_supervisor.LOC_ALIAS
        )

    def test_get_loc_vault_zero_supervisees(self, mock_get_supervisees_for_alias: MagicMock):
        mock_get_supervisees_for_alias.side_effect = mock_supervisor_get_supervisees_for_alias(
            supervisees={
                line_of_credit_supervisor.LOC_ALIAS: [],
                line_of_credit_supervisor.DRAWDOWN_LOAN_ALIAS: [sentinel.dummy2, sentinel.dummy3],
            }
        )
        result = line_of_credit_supervisor._get_loc_vault(sentinel.supervisor)
        self.assertEqual(result, None)
        mock_get_supervisees_for_alias.assert_called_once_with(
            vault=sentinel.supervisor, alias=line_of_credit_supervisor.LOC_ALIAS
        )

    def test_get_loc_vault_multiple_loc_supervisees(
        self, mock_get_supervisees_for_alias: MagicMock
    ):
        mock_get_supervisees_for_alias.side_effect = mock_supervisor_get_supervisees_for_alias(
            supervisees={
                line_of_credit_supervisor.LOC_ALIAS: [sentinel.loc_vault_1, sentinel.loc_vault_2],
                line_of_credit_supervisor.DRAWDOWN_LOAN_ALIAS: [sentinel.dummy2, sentinel.dummy3],
            }
        )
        result = line_of_credit_supervisor._get_loc_vault(sentinel.supervisor)
        self.assertEqual(result, None)
        mock_get_supervisees_for_alias.assert_called_once_with(
            vault=sentinel.supervisor, alias=line_of_credit_supervisor.LOC_ALIAS
        )


@patch.object(line_of_credit_supervisor.close_loan, "does_repayment_fully_repay_loan")
class GetPaidOffLoansNotification(LineOfCreditSupervisorTestBase):
    def setUp(self) -> None:
        self.loan_1 = self.create_supervisee_mock(
            supervisee_alias=line_of_credit_supervisor.DRAWDOWN_LOAN_ALIAS, account_id="loan_1"
        )
        self.loan_2 = self.create_supervisee_mock(
            supervisee_alias=line_of_credit_supervisor.DRAWDOWN_LOAN_ALIAS, account_id="loan_2"
        )
        self.loc = self.create_supervisee_mock(
            supervisee_alias=line_of_credit_supervisor.LOC_ALIAS, account_id="loc"
        )

        self.repayment_custom_instructions_per_loan: dict[str, list[CustomInstruction]] = {
            self.loan_1.account_id: sentinel.loan_1_custom_instructions,
            self.loan_2.account_id: sentinel.loan_2_custom_instructions,
        }

        self.balances_per_target = {
            self.loan_1.account_id: sentinel.loan_1_balances,
            self.loan_2.account_id: sentinel.loan_2_balances,
            self.loc.account_id: sentinel.loc_balances,
        }
        return super().setUp()

    def test_not_all_loans_paid(self, mock_does_repayment_fully_repay_loan: MagicMock):
        mock_does_repayment_fully_repay_loan.side_effect = [True, False]

        expected_paid_off_loans_ids = ["loan_1"]

        expected_result = [
            AccountNotificationDirective(
                notification_type=line_of_credit_supervisor.LOANS_PAID_OFF_NOTIFICATION,
                notification_details={"account_ids": json.dumps(expected_paid_off_loans_ids)},
            )
        ]

        result = line_of_credit_supervisor._get_paid_off_loans_notification(
            repayment_custom_instructions_per_loan=self.repayment_custom_instructions_per_loan,
            balances_per_target=self.balances_per_target,
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, expected_result)

    def test_no_loans_paid_off(self, mock_does_repayment_fully_repay_loan: MagicMock):
        mock_does_repayment_fully_repay_loan.side_effect = [False, False]

        result = line_of_credit_supervisor._get_paid_off_loans_notification(
            repayment_custom_instructions_per_loan=self.repayment_custom_instructions_per_loan,
            balances_per_target=self.balances_per_target,
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, [])


class GetDelinquencyNotification(LineOfCreditSupervisorTestBase):
    def test_delinquency_notification(self):
        result = line_of_credit_supervisor._get_delinquency_notification(
            account_id=sentinel.account_id
        )
        self.assertEqual(
            result,
            [
                AccountNotificationDirective(
                    notification_type=line_of_credit_supervisor.DELINQUENT_NOTIFICATION,
                    notification_details={
                        "account_id": sentinel.account_id,
                    },
                )
            ],
        )


@patch.object(line_of_credit_supervisor.utils, "get_parameter")
class GetDueAmountCalculationDayParameterTest(LineOfCreditSupervisorTestBase):
    param_name = line_of_credit_supervisor.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY

    def test_due_amount_calculation_day_is_returned(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter({self.param_name: "10"})

        result = line_of_credit_supervisor._get_due_amount_calculation_day_parameter(
            loc_vault=sentinel.vault
        )

        self.assertEqual(result, 10)
        mock_get_parameter.assert_called_once_with(
            vault=sentinel.vault, name=self.param_name, at_datetime=None
        )


@patch.object(
    line_of_credit_supervisor.due_amount_calculation, "update_due_amount_calculation_counter"
)
@patch.object(line_of_credit_supervisor.utils, "standard_instruction_details")
class UpdateDueAmountCalculationCountersTest(LineOfCreditSupervisorTestBase):
    def test_update_due_amount_calculation_counters(
        self,
        mock_standard_instruction_details: MagicMock,
        mock_update_due_amount_calculation_counter: MagicMock,
    ):
        mock_loan_1 = self.create_supervisee_mock(account_id="loan_1")
        mock_loan_2 = self.create_supervisee_mock(account_id="loan_2")
        mock_update_due_amount_calculation_counter.return_value = DEFAULT_POSTINGS
        mock_standard_instruction_details.return_value = {}

        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=sentinel.event_type,
            supervisee_pause_at_datetime={},
        )

        expected = {
            "loan_1": [
                PostingInstructionsDirective(
                    posting_instructions=[
                        _CustomInstruction(
                            postings=DEFAULT_POSTINGS,
                            instruction_details={},
                            override_all_restrictions=True,
                        )
                    ],
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
            "loan_2": [
                PostingInstructionsDirective(
                    posting_instructions=[
                        _CustomInstruction(
                            postings=DEFAULT_POSTINGS,
                            instruction_details={},
                            override_all_restrictions=True,
                        )
                    ],
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
        }

        result = line_of_credit_supervisor._update_due_amount_calculation_counters(
            loan_vaults=[mock_loan_1, mock_loan_2],
            hook_arguments=hook_arguments,
            denomination=sentinel.denomination,
        )

        self.assertDictEqual(result, expected)

        mock_update_due_amount_calculation_counter.assert_has_calls(
            calls=[
                call(
                    account_id="loan_1",
                    denomination=sentinel.denomination,
                ),
                call(
                    account_id="loan_2",
                    denomination=sentinel.denomination,
                ),
            ]
        )
        mock_standard_instruction_details.assert_has_calls(
            calls=[
                call(
                    description="Updating due amount calculation counter",
                    event_type=sentinel.event_type,
                    gl_impacted=False,
                    account_type=line_of_credit_supervisor.DRAWDOWN_LOAN_ACCOUNT_TYPE,
                )
            ]
        )
