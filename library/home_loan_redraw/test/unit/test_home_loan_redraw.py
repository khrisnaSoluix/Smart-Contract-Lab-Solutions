# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.

# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel
from zoneinfo import ZoneInfo

# library
from library.home_loan_redraw.contracts.template import home_loan_redraw
from library.home_loan_redraw.test import accounts, parameters

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    ActivationHookArguments,
    ConversionHookArguments,
    Posting,
    PostPostingHookArguments,
    PrePostingHookArguments,
    ScheduledEvent,
    ScheduledEventHookArguments,
    Tside,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_HOOK_EXECUTION_ID,
    ContractTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    AccountNotificationDirective,
    ActivationHookResult,
    Balance,
    BalanceDefaultDict,
    BalancesObservation,
    ConversionHookResult,
    CustomInstruction,
    DeactivationHookArguments,
    DeactivationHookResult,
    DerivedParameterHookArguments,
    DerivedParameterHookResult,
    Phase,
    PostingInstructionsDirective,
    PostPostingHookResult,
    PrePostingHookResult,
    Rejection,
    RejectionReason,
    ScheduledEventHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalance,
    SentinelBalancesObservation,
    SentinelCustomInstruction,
    SentinelPosting,
    SentinelRejection,
    SentinelScheduledEvent,
)

DEFAULT_DATETIME = datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC"))


class HomeLoanRedrawTest(ContractTest):
    account_id = accounts.HOME_LOAN_REDRAW
    tside = Tside.ASSET
    default_denomination = parameters.TEST_DENOMINATION


class ActivationTest(HomeLoanRedrawTest):
    @patch.object(home_loan_redraw.emi, "amortise")
    @patch.object(home_loan_redraw.disbursement, "get_disbursement_custom_instruction")
    @patch.object(home_loan_redraw.due_amount_calculation, "scheduled_events")
    @patch.object(home_loan_redraw.interest_accrual, "scheduled_events")
    @patch.object(home_loan_redraw.utils, "get_parameter")
    def test_activation_schedules_and_posting_directives(
        self,
        mock_get_parameter: MagicMock,
        mock_accrual_scheduled_events: MagicMock,
        mock_due_amount_calc_scheduled_events: MagicMock,
        mock_get_disbursement: MagicMock,
        mock_amortise: MagicMock,
    ):
        accrual_scheduled_events = {
            sentinel.accrual_event_type: SentinelScheduledEvent("accrual_event")
        }
        due_amount_calc_scheduled_events = {
            sentinel.due_amount_calc_event_type: SentinelScheduledEvent("due_amount_calc")
        }
        disbursement_posting_instructions = [SentinelCustomInstruction("disbursal")]
        emi_posting_instructions = [SentinelCustomInstruction("emi")]

        # set mocks to their correct values
        mock_accrual_scheduled_events.return_value = accrual_scheduled_events
        mock_due_amount_calc_scheduled_events.return_value = due_amount_calc_scheduled_events
        mock_get_disbursement.return_value = disbursement_posting_instructions
        mock_amortise.return_value = emi_posting_instructions
        posting_instructions: list[CustomInstruction] = [  # type: ignore
            *disbursement_posting_instructions,
            *emi_posting_instructions,
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
                "principal": Decimal("1000"),
                "deposit_account": sentinel.deposit_account,
            }
        )
        mock_vault = self.create_mock()

        hook_args = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        hook_result = home_loan_redraw.activation_hook(vault=mock_vault, hook_arguments=hook_args)

        self.assertEqual(
            hook_result,
            ActivationHookResult(
                posting_instructions_directives=[
                    PostingInstructionsDirective(
                        posting_instructions=posting_instructions,  # type: ignore
                        client_batch_id="ACCOUNT_ACTIVATION_MOCK_HOOK",
                        value_datetime=DEFAULT_DATETIME,
                    )
                ],
                scheduled_events_return_value={
                    **accrual_scheduled_events,
                    **due_amount_calc_scheduled_events,
                },
            ),
        )
        mock_amortise.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=home_loan_redraw.declining_principal.AmortisationFeature,
            interest_calculation_feature=home_loan_redraw.variable_rate.interest_rate_interface,
        )


@patch.object(home_loan_redraw.utils, "get_parameter")
@patch.object(home_loan_redraw.close_loan, "reject_closure_when_outstanding_debt")
class DeactivationTest(HomeLoanRedrawTest):
    def test_cannot_deactivate_an_account_with_outstanding_debt(
        self, mock_reject_closure_when_outstanding_debt: MagicMock, mock_get_parameter: MagicMock
    ):
        # setup mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                home_loan_redraw.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
            }
        )
        mock_rejection = SentinelRejection("dummy_rejection")
        mock_reject_closure_when_outstanding_debt.return_value = mock_rejection

        hook_args = DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        deactivate_account_result = home_loan_redraw.deactivation_hook(
            vault=mock_vault, hook_arguments=hook_args
        )

        # assertions
        mock_get_parameter.assert_called_once_with(vault=mock_vault, name="denomination")
        mock_reject_closure_when_outstanding_debt.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=self.default_denomination,
        )
        self.assertEqual(
            deactivate_account_result, DeactivationHookResult(rejection=mock_rejection)
        )

    @patch.object(home_loan_redraw.redraw, "reject_closure_when_outstanding_redraw_funds")
    def test_cannot_deactivate_an_account_with_outstanding_redraw_funds(
        self,
        mock_reject_closure_when_outstanding_redraw_funds: MagicMock,
        mock_reject_closure_when_outstanding_debt: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # setup mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                home_loan_redraw.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
            }
        )
        mock_reject_closure_when_outstanding_debt.return_value = None
        mock_rejection = SentinelRejection("dummy_rejection")
        mock_reject_closure_when_outstanding_redraw_funds.return_value = mock_rejection

        hook_args = DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        deactivate_account_result = home_loan_redraw.deactivation_hook(
            vault=mock_vault, hook_arguments=hook_args
        )

        # assertions
        mock_get_parameter.assert_called_once_with(vault=mock_vault, name="denomination")
        mock_reject_closure_when_outstanding_debt.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=self.default_denomination,
        )
        mock_reject_closure_when_outstanding_redraw_funds.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=self.default_denomination,
        )
        self.assertEqual(
            deactivate_account_result, DeactivationHookResult(rejection=mock_rejection)
        )

    @patch.object(
        home_loan_redraw.due_amount_calculation, "DueAmountCalculationResidualCleanupFeature"
    )
    @patch.object(home_loan_redraw.redraw, "reject_closure_when_outstanding_redraw_funds")
    @patch.object(home_loan_redraw.close_loan, "net_balances")
    def test_deactivate_account_returns_none_if_no_net_postings(
        self,
        mock_net_balances: MagicMock,
        mock_reject_closure_when_outstanding_redraw_funds: MagicMock,
        mock_due_amount_calculation_cleanup_feature: MagicMock,
        mock_reject_closure_when_outstanding_debt: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # setup mocks
        mock_vault = self.create_mock(
            account_id=self.account_id,
            balances_observation_fetchers_mapping={
                home_loan_redraw.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
            }
        )
        mock_reject_closure_when_outstanding_debt.return_value = None
        mock_reject_closure_when_outstanding_redraw_funds.return_value = None
        mock_net_balances.return_value = []

        hook_args = DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        deactivate_account_result = home_loan_redraw.deactivation_hook(
            vault=mock_vault, hook_arguments=hook_args
        )

        # assertions
        mock_get_parameter.assert_called_once_with(vault=mock_vault, name="denomination")
        mock_reject_closure_when_outstanding_debt.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=self.default_denomination,
        )
        mock_reject_closure_when_outstanding_redraw_funds.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=self.default_denomination,
        )
        mock_net_balances.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=self.default_denomination,
            account_id=self.account_id,
            residual_cleanup_features=[mock_due_amount_calculation_cleanup_feature],
        )
        self.assertIsNone(deactivate_account_result)

    @patch.object(
        home_loan_redraw.due_amount_calculation, "DueAmountCalculationResidualCleanupFeature"
    )
    @patch.object(home_loan_redraw.redraw, "reject_closure_when_outstanding_redraw_funds")
    @patch.object(home_loan_redraw.close_loan, "net_balances")
    def test_deactivate_account_instructs_postings_to_net_balances(
        self,
        mock_net_balances: MagicMock,
        mock_reject_closure_when_outstanding_redraw_funds: MagicMock,
        mock_due_amount_calculation_cleanup_feature: MagicMock,
        mock_reject_closure_when_outstanding_debt: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # setup mocks
        mock_vault = self.create_mock(
            account_id=self.account_id,
            balances_observation_fetchers_mapping={
                home_loan_redraw.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
            }
        )
        mock_reject_closure_when_outstanding_debt.return_value = None
        mock_reject_closure_when_outstanding_redraw_funds.return_value = None
        mock_postings: list[CustomInstruction] = [
            SentinelCustomInstruction("dummy_posting_instruction")  # type: ignore
        ]
        mock_net_balances.return_value = mock_postings

        hook_args = DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        deactivate_account_result = home_loan_redraw.deactivation_hook(
            vault=mock_vault, hook_arguments=hook_args
        )

        # assertions
        mock_get_parameter.assert_called_once_with(vault=mock_vault, name="denomination")
        mock_reject_closure_when_outstanding_debt.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=self.default_denomination,
        )
        mock_reject_closure_when_outstanding_redraw_funds.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=self.default_denomination,
        )
        mock_net_balances.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=self.default_denomination,
            account_id=self.account_id,
            residual_cleanup_features=[mock_due_amount_calculation_cleanup_feature],
        )
        self.assertEqual(
            deactivate_account_result,
            DeactivationHookResult(
                posting_instructions_directives=[
                    PostingInstructionsDirective(
                        posting_instructions=mock_postings,  # type: ignore
                        value_datetime=DEFAULT_DATETIME,
                    )
                ]
            ),
        )


@patch.object(home_loan_redraw, "_calculate_next_repayment_date")
@patch.object(home_loan_redraw.declining_principal, "term_details")
@patch.object(home_loan_redraw.derived_params, "get_total_remaining_principal")
@patch.object(home_loan_redraw.derived_params, "get_total_outstanding_debt")
@patch.object(home_loan_redraw.derived_params, "get_total_due_amount")
@patch.object(home_loan_redraw.redraw, "get_available_redraw_funds")
@patch.object(home_loan_redraw.utils, "get_parameter")
class DerivedParameterTest(HomeLoanRedrawTest):
    def test_derived_params_are_returned_correctly(
        self,
        mock_get_parameter: MagicMock,
        mock_get_available_redraw_funds: MagicMock,
        mock_get_total_due_amount: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_get_total_remaining_principal: MagicMock,
        mock_term_details: MagicMock,
        mock_calculate_next_repayment_date: MagicMock,
    ):
        # setup mocks
        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATETIME,
            balances_observation_fetchers_mapping={
                home_loan_redraw.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                    SentinelBalancesObservation("dummy_balances_observation")
                )
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
                "total_repayment_count": sentinel.total_repayment_count,
            }
        )
        mock_term_details.return_value = sentinel.elapsed_term, sentinel.remaining_term

        # the total remaining principal and the available redraw funds
        # are needed to calculate the remaining principal left to be paid,
        # which is an input to "calculate_remaining_term"
        mock_get_available_redraw_funds.return_value = Decimal("10")
        mock_calculate_next_repayment_date.return_value = sentinel.next_repayment_date
        mock_get_total_outstanding_debt.return_value = sentinel.total_outstanding_debt
        mock_get_total_due_amount.return_value = sentinel.total_due_amount
        mock_get_total_remaining_principal.return_value = Decimal("100")

        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)
        derived_param_hook_result: DerivedParameterHookResult = (
            home_loan_redraw.derived_parameter_hook(vault=mock_vault, hook_arguments=hook_args)
        )

        mock_get_parameter.assert_has_calls(
            [
                call(vault=mock_vault, name="denomination"),
            ]
        )
        mock_get_available_redraw_funds.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_calculate_next_repayment_date.assert_called_once_with(
            vault=mock_vault,
            derived_parameter_hook_args=hook_args,
        )
        mock_get_total_outstanding_debt.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_total_due_amount.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_total_remaining_principal.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        expected_derived_params = {
            "available_redraw_funds": Decimal("10"),
            "next_repayment_date": sentinel.next_repayment_date,
            "remaining_term": sentinel.remaining_term,
            "total_outstanding_debt": sentinel.total_outstanding_debt,
            "total_outstanding_payments": sentinel.total_due_amount,
            "total_remaining_principal": Decimal("100"),
        }

        self.assertEqual(
            derived_param_hook_result,
            DerivedParameterHookResult(
                parameters_return_value=expected_derived_params  # type: ignore
            ),
        )


@patch.object(home_loan_redraw.due_amount_calculation, "get_first_due_amount_calculation_datetime")
@patch.object(home_loan_redraw.utils, "get_parameter")
class CalculateNextRepaymentDateTest(HomeLoanRedrawTest):
    def test_next_repayment_date_is_first_due_date_before_first_due_date(
        self,
        mock_get_parameter: MagicMock,
        mock_get_first_due_amount_calculation_datetime: MagicMock,
    ):

        first_due_date = DEFAULT_DATETIME + relativedelta(months=1)

        # setup mocks
        mock_vault = self.create_mock()
        mock_get_first_due_amount_calculation_datetime.return_value = first_due_date

        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)
        actual_next_repayment_date = home_loan_redraw._calculate_next_repayment_date(
            vault=mock_vault, derived_parameter_hook_args=hook_args
        )

        # assertions
        mock_get_first_due_amount_calculation_datetime.assert_called_once_with(vault=mock_vault)
        mock_get_parameter.assert_not_called()
        self.assertEqual(actual_next_repayment_date, first_due_date)

    def test_next_repayment_date_is_first_due_date_on_first_due_date(
        self,
        mock_get_parameter: MagicMock,
        mock_get_first_due_amount_calculation_datetime: MagicMock,
    ):

        first_due_date = DEFAULT_DATETIME + relativedelta(months=1)

        # setup mocks
        mock_vault = self.create_mock()
        mock_get_first_due_amount_calculation_datetime.return_value = first_due_date

        hook_args = DerivedParameterHookArguments(
            effective_datetime=first_due_date + relativedelta(hours=23)
        )
        actual_next_repayment_date = home_loan_redraw._calculate_next_repayment_date(
            vault=mock_vault, derived_parameter_hook_args=hook_args
        )

        # assertions
        mock_get_first_due_amount_calculation_datetime.assert_called_once_with(vault=mock_vault)
        mock_get_parameter.assert_not_called()
        self.assertEqual(actual_next_repayment_date, first_due_date)

    def test_next_repayment_date_is_second_due_date_after_first_due_date(
        self,
        mock_get_parameter: MagicMock,
        mock_get_first_due_amount_calculation_datetime: MagicMock,
    ):

        first_due_date = DEFAULT_DATETIME + relativedelta(months=1)
        second_due_date = DEFAULT_DATETIME + relativedelta(months=2)

        # setup mocks
        mock_vault = self.create_mock()
        mock_get_first_due_amount_calculation_datetime.return_value = first_due_date
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "due_amount_calculation_day": 1,
            }
        )

        hook_args = DerivedParameterHookArguments(
            effective_datetime=first_due_date + relativedelta(hours=24)
        )
        actual_next_repayment_date = home_loan_redraw._calculate_next_repayment_date(
            vault=mock_vault, derived_parameter_hook_args=hook_args
        )

        # assertions
        mock_get_first_due_amount_calculation_datetime.assert_called_once_with(vault=mock_vault)
        mock_get_parameter.assert_called_once_with(
            vault=mock_vault, name="due_amount_calculation_day"
        )
        self.assertEqual(actual_next_repayment_date, second_due_date)

    def test_next_repayment_date_is_second_due_date_on_second_due_date(
        self,
        mock_get_parameter: MagicMock,
        mock_get_first_due_amount_calculation_datetime: MagicMock,
    ):

        first_due_date = DEFAULT_DATETIME + relativedelta(months=1)
        second_due_date = DEFAULT_DATETIME + relativedelta(months=2)

        # setup mocks
        mock_vault = self.create_mock()
        mock_get_first_due_amount_calculation_datetime.return_value = first_due_date
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "due_amount_calculation_day": 1,
            }
        )

        hook_args = DerivedParameterHookArguments(
            effective_datetime=second_due_date + relativedelta(hours=23)
        )
        actual_next_repayment_date = home_loan_redraw._calculate_next_repayment_date(
            vault=mock_vault, derived_parameter_hook_args=hook_args
        )

        # assertions
        mock_get_first_due_amount_calculation_datetime.assert_called_once_with(vault=mock_vault)
        mock_get_parameter.assert_called_once_with(
            vault=mock_vault, name="due_amount_calculation_day"
        )
        self.assertEqual(actual_next_repayment_date, second_due_date)


class ScheduledEventTest(HomeLoanRedrawTest):
    @patch.object(home_loan_redraw.interest_accrual, "daily_accrual_logic")
    def test_interest_accrual_with_accrual_returns_posting_directive(
        self,
        mock_daily_accrual_logic: MagicMock,
    ):
        accrual_cis: list[CustomInstruction] = [SentinelCustomInstruction("test")]  # type: ignore
        mock_daily_accrual_logic.return_value = accrual_cis
        mock_vault = sentinel.vault
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=home_loan_redraw.interest_accrual.ACCRUAL_EVENT,
        )
        hook_result = home_loan_redraw.scheduled_event_hook(
            vault=mock_vault, hook_arguments=hook_args
        )

        self.assertEqual(
            hook_result,
            ScheduledEventHookResult(
                posting_instructions_directives=[
                    PostingInstructionsDirective(
                        posting_instructions=accrual_cis,  # type: ignore
                        value_datetime=DEFAULT_DATETIME,
                    )
                ]
            ),
        )
        mock_daily_accrual_logic.assert_called_once_with(
            vault=mock_vault,
            interest_rate_feature=home_loan_redraw.variable_rate.interest_rate_interface,
            hook_arguments=hook_args,
            account_type=home_loan_redraw.PRODUCT_NAME,
            principal_addresses=["PRINCIPAL", "REDRAW"],
        )

    @patch.object(home_loan_redraw.interest_accrual, "daily_accrual_logic")
    def test_interest_accrual_without_accrual_returns_none(
        self,
        mock_daily_accrual_logic: MagicMock,
    ):
        mock_daily_accrual_logic.return_value = []
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=home_loan_redraw.interest_accrual.ACCRUAL_EVENT,
        )
        hook_result = home_loan_redraw.scheduled_event_hook(
            vault=sentinel.vault, hook_arguments=hook_args
        )

        self.assertIsNone(hook_result)

    @patch.object(home_loan_redraw.due_amount_calculation, "schedule_logic")
    @patch.object(home_loan_redraw.redraw, "auto_repayment")
    @patch.object(home_loan_redraw.utils, "get_parameter")
    @patch.object(home_loan_redraw.close_loan, "does_repayment_fully_repay_loan")
    def test_due_amount_calc_returns_posting_directive(
        self,
        mock_does_repayment_fully_repay_loan: MagicMock,
        mock_get_parameter: MagicMock,
        mock_auto_repayment: MagicMock,
        mock_due_amount_calc_scheduled_logic: MagicMock,
    ):
        due_amount_calc_cis: list[CustomInstruction] = [
            SentinelCustomInstruction("due_amount_calc")  # type: ignore
        ]
        mock_due_amount_calc_scheduled_logic.return_value = due_amount_calc_cis
        mock_vault = self.create_mock(
            account_id=self.account_id,
            balances_observation_fetchers_mapping={
                home_loan_redraw.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                    SentinelBalancesObservation("dummy_balances_observation")
                )
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
            }
        )
        mock_auto_repayment.return_value = []
        mock_does_repayment_fully_repay_loan.return_value = False

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=home_loan_redraw.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
        )
        hook_result = home_loan_redraw.scheduled_event_hook(
            vault=mock_vault, hook_arguments=hook_args
        )

        self.assertEqual(
            hook_result,
            ScheduledEventHookResult(
                posting_instructions_directives=[
                    PostingInstructionsDirective(
                        posting_instructions=due_amount_calc_cis,  # type: ignore
                        value_datetime=DEFAULT_DATETIME,
                    )
                ]
            ),
        )
        mock_get_parameter.assert_called_once_with(
            vault=mock_vault,
            name="denomination",
        )
        mock_due_amount_calc_scheduled_logic.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            account_type=home_loan_redraw.PRODUCT_NAME,
            interest_application_feature=home_loan_redraw.interest_application.InterestApplication,
            amortisation_feature=home_loan_redraw.declining_principal.AmortisationFeature,
        )
        mock_auto_repayment.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            due_amount_posting_instructions=due_amount_calc_cis,
            denomination=self.default_denomination,
            account_id=self.account_id,
            repayment_hierarchy=home_loan_redraw.REPAYMENT_HIERARCHY,
        )
        mock_does_repayment_fully_repay_loan.assert_called_once_with(
            repayment_posting_instructions=[],
            balances=sentinel.balances_dummy_balances_observation,
            denomination=self.default_denomination,
            account_id=self.account_id,
        )

    @patch.object(home_loan_redraw.due_amount_calculation, "schedule_logic")
    @patch.object(home_loan_redraw.redraw, "auto_repayment")
    @patch.object(home_loan_redraw.utils, "get_parameter")
    @patch.object(home_loan_redraw.close_loan, "does_repayment_fully_repay_loan")
    def test_due_amount_calc_without_calc_returns_none(
        self,
        mock_does_repayment_fully_repay_loan: MagicMock,
        mock_get_parameter: MagicMock,
        mock_auto_repayment: MagicMock,
        mock_due_amount_calc_scheduled_logic: MagicMock,
    ):
        mock_due_amount_calc_scheduled_logic.return_value = []
        mock_vault = self.create_mock(
            account_id=self.account_id,
            balances_observation_fetchers_mapping={
                home_loan_redraw.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                    SentinelBalancesObservation("dummy_balances_observation")
                )
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
            }
        )
        mock_auto_repayment.return_value = []
        mock_does_repayment_fully_repay_loan.return_value = False

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=home_loan_redraw.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
        )
        hook_result = home_loan_redraw.scheduled_event_hook(
            vault=mock_vault, hook_arguments=hook_args
        )

        # assertions
        mock_does_repayment_fully_repay_loan.assert_called_once_with(
            repayment_posting_instructions=[],
            balances=sentinel.balances_dummy_balances_observation,
            denomination=self.default_denomination,
            account_id=self.account_id,
        )
        self.assertIsNone(hook_result)

    @patch.object(home_loan_redraw.due_amount_calculation, "schedule_logic")
    @patch.object(home_loan_redraw.redraw, "auto_repayment")
    @patch.object(home_loan_redraw.utils, "get_parameter")
    @patch.object(home_loan_redraw.close_loan, "does_repayment_fully_repay_loan")
    def test_due_amount_calc_with_auto_repayment_returns_posting_directive_and_no_notification(
        self,
        mock_does_repayment_fully_repay_loan: MagicMock,
        mock_get_parameter: MagicMock,
        mock_auto_repayment: MagicMock,
        mock_due_amount_calc_scheduled_logic: MagicMock,
    ):
        due_amount_calc_posting_instruction: list[CustomInstruction] = [
            SentinelCustomInstruction("dummy_due_amt_custom_instruction")  # type: ignore
        ]
        mock_due_amount_calc_scheduled_logic.return_value = due_amount_calc_posting_instruction
        mock_vault = self.create_mock(
            account_id=self.account_id,
            balances_observation_fetchers_mapping={
                home_loan_redraw.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                    SentinelBalancesObservation("dummy_balances_observation")
                )
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
            }
        )
        auto_repayment_posting_instruction = [
            SentinelCustomInstruction("dummy_auto_repayment_posting_instruction")
        ]
        mock_auto_repayment.return_value = auto_repayment_posting_instruction
        mock_does_repayment_fully_repay_loan.return_value = False

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=home_loan_redraw.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
        )
        hook_result = home_loan_redraw.scheduled_event_hook(
            vault=mock_vault, hook_arguments=hook_args
        )

        # assertions
        self.assertEqual(
            hook_result,
            ScheduledEventHookResult(
                account_notification_directives=[],
                posting_instructions_directives=[
                    PostingInstructionsDirective(
                        posting_instructions=due_amount_calc_posting_instruction
                        + auto_repayment_posting_instruction,  # type: ignore
                        value_datetime=DEFAULT_DATETIME,
                    )
                ],
            ),
        )
        mock_get_parameter.assert_called_once_with(
            vault=mock_vault,
            name="denomination",
        )
        mock_due_amount_calc_scheduled_logic.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            account_type=home_loan_redraw.PRODUCT_NAME,
            interest_application_feature=home_loan_redraw.interest_application.InterestApplication,
            amortisation_feature=home_loan_redraw.declining_principal.AmortisationFeature,
        )
        mock_auto_repayment.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            due_amount_posting_instructions=due_amount_calc_posting_instruction,
            denomination=self.default_denomination,
            account_id=self.account_id,
            repayment_hierarchy=home_loan_redraw.REPAYMENT_HIERARCHY,
        )
        mock_does_repayment_fully_repay_loan.assert_called_once_with(
            repayment_posting_instructions=auto_repayment_posting_instruction,
            balances=sentinel.balances_dummy_balances_observation,
            denomination=self.default_denomination,
            account_id=self.account_id,
        )

    @patch.object(home_loan_redraw.due_amount_calculation, "schedule_logic")
    @patch.object(home_loan_redraw.redraw, "auto_repayment")
    @patch.object(home_loan_redraw.utils, "get_parameter")
    @patch.object(home_loan_redraw.close_loan, "does_repayment_fully_repay_loan")
    def test_full_auto_repayment_with_excess_redraw_funds_returns_notification(
        self,
        mock_does_repayment_fully_repay_loan: MagicMock,
        mock_get_parameter: MagicMock,
        mock_auto_repayment: MagicMock,
        mock_due_amount_calc_scheduled_logic: MagicMock,
    ):
        due_amount_calc_posting_instruction: list[CustomInstruction] = [
            SentinelCustomInstruction("dummy_due_amt_custom_instruction")  # type: ignore
        ]
        mock_due_amount_calc_scheduled_logic.return_value = due_amount_calc_posting_instruction
        mock_vault = self.create_mock(
            account_id=self.account_id,
            balances_observation_fetchers_mapping={
                home_loan_redraw.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                    SentinelBalancesObservation("dummy_balances_observation")
                )
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
            }
        )
        auto_repayment_posting_instruction = [
            SentinelCustomInstruction("dummy_auto_repayment_posting_instruction")
        ]
        mock_auto_repayment.return_value = auto_repayment_posting_instruction
        mock_does_repayment_fully_repay_loan.return_value = True

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=home_loan_redraw.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
        )
        hook_result = home_loan_redraw.scheduled_event_hook(
            vault=mock_vault, hook_arguments=hook_args
        )

        # assertions
        self.assertEqual(
            hook_result,
            ScheduledEventHookResult(
                account_notification_directives=[
                    AccountNotificationDirective(
                        notification_type="HOME_LOAN_REDRAW_PAID_OFF",
                        notification_details={"account_id": self.account_id},
                    )
                ],
                posting_instructions_directives=[
                    PostingInstructionsDirective(
                        posting_instructions=due_amount_calc_posting_instruction
                        + auto_repayment_posting_instruction,  # type: ignore
                        value_datetime=DEFAULT_DATETIME,
                    )
                ],
            ),
        )
        mock_get_parameter.assert_called_once_with(
            vault=mock_vault,
            name="denomination",
        )
        mock_due_amount_calc_scheduled_logic.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            account_type=home_loan_redraw.PRODUCT_NAME,
            interest_application_feature=home_loan_redraw.interest_application.InterestApplication,
            amortisation_feature=home_loan_redraw.declining_principal.AmortisationFeature,
        )
        mock_auto_repayment.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            due_amount_posting_instructions=due_amount_calc_posting_instruction,
            denomination=self.default_denomination,
            account_id=self.account_id,
            repayment_hierarchy=home_loan_redraw.REPAYMENT_HIERARCHY,
        )
        mock_does_repayment_fully_repay_loan.assert_called_once_with(
            repayment_posting_instructions=auto_repayment_posting_instruction,
            balances=sentinel.balances_dummy_balances_observation,
            denomination=self.default_denomination,
            account_id=self.account_id,
        )


@patch.object(home_loan_redraw.utils, "is_force_override")
class PrePostingTest(HomeLoanRedrawTest):
    def test_pre_posting_with_force_override_overrides_rejections_and_is_accepted(
        self,
        mock_is_force_override: MagicMock,
    ):
        postings = SentinelCustomInstruction("dummy_posting")

        # setup mocks
        mock_vault = sentinel.vault
        mock_is_force_override.return_value = True

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=postings,
            client_transactions={},
        )
        pre_posting_result = home_loan_redraw.pre_posting_hook(mock_vault, hook_args)

        # assertions
        mock_is_force_override.assert_called_once_with(posting_instructions=postings)
        self.assertIsNone(pre_posting_result)

    @patch.object(home_loan_redraw.utils, "get_parameter")
    @patch.object(home_loan_redraw.utils, "validate_denomination")
    def test_posting_with_wrong_denomination_is_rejected(
        self,
        mock_validate_denomination: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        postings = SentinelCustomInstruction("dummy_posting")
        rejection = SentinelRejection("dummy_rejection")

        # setup mocks
        mock_vault = sentinel.vault
        mock_is_force_override.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
            }
        )
        mock_validate_denomination.return_value = rejection

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=postings,
            client_transactions={},
        )
        pre_posting_result = home_loan_redraw.pre_posting_hook(mock_vault, hook_args)

        # assertions
        mock_is_force_override.assert_called_once_with(posting_instructions=postings)
        mock_get_parameter.assert_called_once_with(vault=mock_vault, name="denomination")
        mock_validate_denomination.assert_called_once_with(
            posting_instructions=postings, accepted_denominations=[self.default_denomination]
        )
        self.assertEqual(pre_posting_result, PrePostingHookResult(rejection=rejection))

    @patch.object(home_loan_redraw.utils, "get_parameter")
    @patch.object(home_loan_redraw.utils, "validate_denomination")
    @patch.object(home_loan_redraw.utils, "validate_single_hard_settlement_or_transfer")
    def test_wrong_posting_type_is_rejected(
        self,
        mock_validate_single_hard_settlement: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        postings = SentinelCustomInstruction("dummy_posting")
        rejection = SentinelRejection("dummy_rejection")

        # setup mocks
        mock_vault = sentinel.vault
        mock_is_force_override.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
            }
        )
        mock_validate_denomination.return_value = None
        mock_validate_single_hard_settlement.return_value = rejection

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=postings,
            client_transactions={},
        )
        pre_posting_result = home_loan_redraw.pre_posting_hook(mock_vault, hook_args)

        # assertions
        mock_is_force_override.assert_called_once_with(posting_instructions=postings)
        mock_get_parameter.assert_called_once_with(vault=mock_vault, name="denomination")
        mock_validate_denomination.assert_called_once_with(
            posting_instructions=postings, accepted_denominations=[self.default_denomination]
        )
        mock_validate_single_hard_settlement.assert_called_once_with(posting_instructions=postings)
        self.assertEqual(pre_posting_result, PrePostingHookResult(rejection=rejection))

    @patch.object(home_loan_redraw.utils, "get_parameter")
    @patch.object(home_loan_redraw.utils, "validate_denomination")
    @patch.object(home_loan_redraw.utils, "validate_single_hard_settlement_or_transfer")
    def test_empty_posting_array_is_rejected(
        self,
        mock_validate_single_hard_settlement: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        postings: list[Posting] = []
        rejection = SentinelRejection("dummy_rejection")

        # setup mocks
        mock_vault = sentinel.vault
        mock_is_force_override.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
            }
        )
        mock_validate_denomination.return_value = None
        mock_validate_single_hard_settlement.return_value = rejection

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=postings,
            client_transactions={},
        )
        pre_posting_result = home_loan_redraw.pre_posting_hook(mock_vault, hook_args)

        # assertions
        mock_is_force_override.assert_called_once_with(posting_instructions=postings)
        mock_get_parameter.assert_called_once_with(vault=mock_vault, name="denomination")
        mock_validate_denomination.assert_called_once_with(
            posting_instructions=postings, accepted_denominations=[self.default_denomination]
        )
        mock_validate_single_hard_settlement.assert_called_once_with(posting_instructions=postings)
        self.assertEqual(pre_posting_result, PrePostingHookResult(rejection=rejection))

    @patch.object(home_loan_redraw.utils, "get_parameter")
    @patch.object(home_loan_redraw.utils, "validate_denomination")
    @patch.object(home_loan_redraw.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(home_loan_redraw.redraw, "validate_redraw_funds")
    def test_posting_with_invalid_redraw_funds_is_rejected(
        self,
        mock_validate_redraw_funds: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        posting_instructions = [self.outbound_hard_settlement(amount=Decimal(100))]
        rejection = SentinelRejection("dummy_rejection")
        balances = BalanceDefaultDict(
            mapping={
                self.balance_coordinate(
                    account_address=DEFAULT_ADDRESS,
                    phase=Phase.COMMITTED,
                    denomination=self.default_denomination,
                    asset=DEFAULT_ASSET,
                ): Balance(net=Decimal(100))
            }
        )

        # setup mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                home_loan_redraw.fetchers.LIVE_BALANCES_BOF_ID: BalancesObservation(
                    balances=balances
                )
            },
        )
        mock_is_force_override.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
            }
        )
        mock_validate_denomination.return_value = None
        mock_validate_single_hard_settlement.return_value = None
        mock_validate_redraw_funds.return_value = rejection

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=posting_instructions,
            client_transactions={},
        )
        pre_posting_result = home_loan_redraw.pre_posting_hook(mock_vault, hook_args)

        # assertions
        mock_is_force_override.assert_called_once_with(posting_instructions=posting_instructions)
        mock_get_parameter.assert_called_once_with(vault=mock_vault, name="denomination")
        mock_validate_denomination.assert_called_once_with(
            posting_instructions=posting_instructions,
            accepted_denominations=[self.default_denomination],
        )
        mock_validate_single_hard_settlement.assert_called_once_with(
            posting_instructions=posting_instructions
        )
        mock_validate_redraw_funds.assert_called_once_with(
            balances=balances, posting_amount=Decimal(100), denomination=self.default_denomination
        )
        self.assertEqual(pre_posting_result, PrePostingHookResult(rejection=rejection))

    @patch.object(home_loan_redraw.utils, "get_parameter")
    @patch.object(home_loan_redraw.utils, "validate_denomination")
    @patch.object(home_loan_redraw.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(home_loan_redraw.redraw, "get_available_redraw_funds")
    @patch.object(home_loan_redraw.redraw, "validate_redraw_funds")
    @patch.object(home_loan_redraw.derived_params, "get_total_outstanding_debt")
    def test_posting_greater_than_total_outstanding_debt_with_no_redraw_is_rejected(
        self,
        mock_total_outstanding_debt: MagicMock,
        mock_validate_redraw_funds: MagicMock,
        mock_get_available_redraw_funds: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        # setup mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                home_loan_redraw.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "dummy_balance_observation"
                )
            },
        )
        mock_is_force_override.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
            }
        )
        mock_validate_denomination.return_value = None
        mock_validate_single_hard_settlement.return_value = None
        mock_validate_redraw_funds.return_value = None
        mock_total_outstanding_debt.return_value = Decimal("89.99")
        mock_get_available_redraw_funds.return_value = Decimal("0.00")

        posting_instructions = [self.inbound_hard_settlement(amount=Decimal(90))]
        # Expected outcome
        rejection = Rejection(
            message="Cannot make a payment of 90 AUD "
            "greater than the net difference of the total outstanding debt of 89.99 "
            "AUD and the remaining redraw balance of 0.00 AUD.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=posting_instructions,
            client_transactions={},
        )
        pre_posting_result = home_loan_redraw.pre_posting_hook(mock_vault, hook_args)

        # assertions
        mock_is_force_override.assert_called_once_with(posting_instructions=posting_instructions)
        mock_get_parameter.assert_called_once_with(vault=mock_vault, name="denomination")
        mock_validate_denomination.assert_called_once_with(
            posting_instructions=posting_instructions,
            accepted_denominations=[self.default_denomination],
        )
        mock_validate_single_hard_settlement.assert_called_once_with(
            posting_instructions=posting_instructions
        )
        mock_validate_redraw_funds.assert_called_once_with(
            balances=sentinel.balances_dummy_balance_observation,
            posting_amount=Decimal(-90),
            denomination=self.default_denomination,
        )
        mock_total_outstanding_debt.assert_called_once_with(
            balances=sentinel.balances_dummy_balance_observation,
            denomination=self.default_denomination,
        )
        mock_get_available_redraw_funds.assert_called_once_with(
            balances=sentinel.balances_dummy_balance_observation,
            denomination=self.default_denomination,
        )
        self.assertEqual(pre_posting_result, PrePostingHookResult(rejection=rejection))

    @patch.object(home_loan_redraw.utils, "get_parameter")
    @patch.object(home_loan_redraw.utils, "validate_denomination")
    @patch.object(home_loan_redraw.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(home_loan_redraw.redraw, "get_available_redraw_funds")
    @patch.object(home_loan_redraw.redraw, "validate_redraw_funds")
    @patch.object(home_loan_redraw.derived_params, "get_total_outstanding_debt")
    def test_posting_greater_than_total_outstanding_debt_net_redraw_is_rejected(
        self,
        mock_total_outstanding_debt: MagicMock,
        mock_validate_redraw_funds: MagicMock,
        mock_get_available_redraw_funds: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        # setup mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                home_loan_redraw.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "dummy_balance_observation"
                )
            },
        )
        mock_is_force_override.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
            }
        )
        mock_validate_denomination.return_value = None
        mock_validate_single_hard_settlement.return_value = None
        mock_validate_redraw_funds.return_value = None
        mock_total_outstanding_debt.return_value = Decimal("100.00")
        mock_get_available_redraw_funds.return_value = Decimal("10.01")

        posting_instructions = [self.inbound_hard_settlement(amount=Decimal(90))]
        # Expected outcome
        rejection = Rejection(
            message="Cannot make a payment of 90 AUD "
            "greater than the net difference of the total outstanding debt of 100.00 "
            "AUD and the remaining redraw balance of 10.01 AUD.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=posting_instructions,
            client_transactions={},
        )
        pre_posting_result = home_loan_redraw.pre_posting_hook(mock_vault, hook_args)

        # assertions
        mock_is_force_override.assert_called_once_with(posting_instructions=posting_instructions)
        mock_get_parameter.assert_called_once_with(vault=mock_vault, name="denomination")
        mock_validate_denomination.assert_called_once_with(
            posting_instructions=posting_instructions,
            accepted_denominations=[self.default_denomination],
        )
        mock_validate_single_hard_settlement.assert_called_once_with(
            posting_instructions=posting_instructions
        )
        mock_validate_redraw_funds.assert_called_once_with(
            balances=sentinel.balances_dummy_balance_observation,
            posting_amount=Decimal(-90),
            denomination=self.default_denomination,
        )
        mock_total_outstanding_debt.assert_called_once_with(
            balances=sentinel.balances_dummy_balance_observation,
            denomination=self.default_denomination,
        )
        mock_get_available_redraw_funds.assert_called_once_with(
            balances=sentinel.balances_dummy_balance_observation,
            denomination=self.default_denomination,
        )
        self.assertEqual(pre_posting_result, PrePostingHookResult(rejection=rejection))

    @patch.object(home_loan_redraw.utils, "get_parameter")
    @patch.object(home_loan_redraw.utils, "validate_denomination")
    @patch.object(home_loan_redraw.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(home_loan_redraw.redraw, "get_available_redraw_funds")
    @patch.object(home_loan_redraw.redraw, "validate_redraw_funds")
    @patch.object(home_loan_redraw.derived_params, "get_total_outstanding_debt")
    def test_valid_posting_is_accepted(
        self,
        mock_get_total_outstanding_debt: MagicMock,
        mock_validate_redraw_funds: MagicMock,
        mock_get_available_redraw_funds: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_get_parameter: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        posting_instructions = [self.custom_instruction([SentinelPosting("dummy_posting")])]

        # setup mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                home_loan_redraw.fetchers.LIVE_BALANCES_BOF_ID: BalancesObservation(
                    balances=BalanceDefaultDict(
                        mapping={self.balance_coordinate(): SentinelBalance("dummy_balance")}
                    )
                )
            },
        )
        mock_is_force_override.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
            }
        )
        mock_validate_denomination.return_value = None
        mock_validate_single_hard_settlement.return_value = None
        mock_validate_redraw_funds.return_value = None
        mock_get_total_outstanding_debt.return_value = Decimal("0")
        mock_get_available_redraw_funds.return_value = Decimal("0")

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=posting_instructions,
            client_transactions={},
        )
        pre_posting_result = home_loan_redraw.pre_posting_hook(mock_vault, hook_args)

        # assertions
        mock_is_force_override.assert_called_once_with(posting_instructions=posting_instructions)
        mock_get_parameter.assert_called_once_with(vault=mock_vault, name="denomination")
        mock_validate_denomination.assert_called_once_with(
            posting_instructions=posting_instructions,
            accepted_denominations=[self.default_denomination],
        )
        mock_validate_single_hard_settlement.assert_called_once_with(
            posting_instructions=posting_instructions
        )
        self.assertIsNone(pre_posting_result)


@patch.object(home_loan_redraw.utils, "get_parameter")
class PostPostingTest(HomeLoanRedrawTest):
    def test_post_posting_posting_with_no_amount_returns_none(
        self,
        mock_get_parameter: MagicMock,
    ):
        posting_instruction = self.custom_instruction([SentinelPosting("dummy_posting")])
        posting_instructions = [posting_instruction]

        # setup mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                home_loan_redraw.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
            }
        )

        hook_args = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=posting_instructions,
            client_transactions={},
        )
        post_posting_result = home_loan_redraw.post_posting_hook(mock_vault, hook_args)

        # assertions
        mock_get_parameter.assert_called_once_with(vault=mock_vault, name="denomination")
        self.assertIsNone(post_posting_result)

    @patch.object(home_loan_redraw.redraw, "OverpaymentFeature")
    @patch.object(home_loan_redraw.payments, "generate_repayment_postings")
    @patch.object(home_loan_redraw.close_loan, "does_repayment_fully_repay_loan")
    def test_post_posting_with_no_repayments_returns_none(
        self,
        mock_does_repayment_fully_repay_loan: MagicMock,
        mock_generate_repayment_postings: MagicMock,
        mock_overpayment_feature: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # setup postings
        postings_amount = Decimal(10.50)
        posting_instruction = self.inbound_hard_settlement(amount=postings_amount)
        postings = [posting_instruction]

        # setup mocks
        mock_vault = self.create_mock(
            account_id=self.account_id,
            balances_observation_fetchers_mapping={
                home_loan_redraw.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
            }
        )
        mock_generate_repayment_postings.return_value = []
        mock_overpayment_feature.handle_overpayment.return_value = []
        mock_does_repayment_fully_repay_loan.return_value = False

        hook_args = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=postings,
            client_transactions={},
        )
        post_posting_result = home_loan_redraw.post_posting_hook(
            vault=mock_vault, hook_arguments=hook_args
        )

        # assertions
        mock_get_parameter.assert_called_once_with(vault=mock_vault, name="denomination")
        mock_generate_repayment_postings.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            repayment_hierarchy=home_loan_redraw.REPAYMENT_HIERARCHY,
            overpayment_features=[mock_overpayment_feature],
        )
        mock_does_repayment_fully_repay_loan.assert_called_once_with(
            repayment_posting_instructions=[],
            balances=sentinel.balances_dummy_balances_observation,
            denomination=self.default_denomination,
            account_id=self.account_id,
        )
        self.assertIsNone(post_posting_result)

    @patch.object(home_loan_redraw.redraw, "OverpaymentFeature")
    @patch.object(home_loan_redraw.payments, "generate_repayment_postings")
    @patch.object(home_loan_redraw.close_loan, "does_repayment_fully_repay_loan")
    def test_post_posting_partial_repayment_returns_posting_directives_and_no_notification(
        self,
        mock_does_repayment_fully_repay_loan: MagicMock,
        mock_generate_repayment_postings: MagicMock,
        mock_overpayment_feature: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # setup postings
        postings_amount = Decimal(10.50)
        posting_instruction = self.inbound_hard_settlement(amount=postings_amount)
        postings = [posting_instruction]

        # setup mocks
        mock_vault = self.create_mock(
            account_id=self.account_id,
            balances_observation_fetchers_mapping={
                home_loan_redraw.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
            }
        )
        mock_posting_instructions = [SentinelCustomInstruction("dummy_posting_instruction")]
        mock_generate_repayment_postings.return_value = mock_posting_instructions
        mock_overpayment_feature.handle_overpayment.return_value = []
        mock_does_repayment_fully_repay_loan.return_value = False

        hook_args = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=postings,
            client_transactions={},
        )
        post_posting_result = home_loan_redraw.post_posting_hook(
            vault=mock_vault, hook_arguments=hook_args
        )

        # assertions
        mock_get_parameter.assert_called_once_with(vault=mock_vault, name="denomination")
        mock_generate_repayment_postings.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            repayment_hierarchy=home_loan_redraw.REPAYMENT_HIERARCHY,
            overpayment_features=[mock_overpayment_feature],
        )
        mock_does_repayment_fully_repay_loan.assert_called_once_with(
            repayment_posting_instructions=mock_posting_instructions,
            balances=sentinel.balances_dummy_balances_observation,
            denomination=self.default_denomination,
            account_id=self.account_id,
        )
        expected_result = PostPostingHookResult(
            account_notification_directives=[],
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=mock_posting_instructions,  # type: ignore
                    client_batch_id=f"{DEFAULT_HOOK_EXECUTION_ID}",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
        )
        self.assertEqual(post_posting_result, expected_result)

    @patch.object(home_loan_redraw.redraw, "OverpaymentFeature")
    @patch.object(home_loan_redraw.payments, "generate_repayment_postings")
    @patch.object(home_loan_redraw.close_loan, "does_repayment_fully_repay_loan")
    def test_post_posting_full_exact_repayment_returns_correct_posting_directives_and_notification(
        self,
        mock_does_repayment_fully_repay_loan: MagicMock,
        mock_generate_repayment_postings: MagicMock,
        mock_overpayment_feature: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # setup postings
        postings_amount = Decimal(10.50)
        posting_instruction = self.inbound_hard_settlement(amount=postings_amount)
        postings = [posting_instruction]

        # setup mocks
        mock_vault = self.create_mock(
            account_id=self.account_id,
            balances_observation_fetchers_mapping={
                home_loan_redraw.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
            }
        )
        mock_posting_instructions = [SentinelCustomInstruction("dummy_posting_instruction")]
        mock_generate_repayment_postings.return_value = mock_posting_instructions
        mock_overpayment_feature.handle_overpayment.return_value = []
        mock_does_repayment_fully_repay_loan.return_value = True

        hook_args = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=postings,
            client_transactions={},
        )
        post_posting_result = home_loan_redraw.post_posting_hook(
            vault=mock_vault, hook_arguments=hook_args
        )

        # assertions
        mock_get_parameter.assert_called_once_with(vault=mock_vault, name="denomination")
        mock_generate_repayment_postings.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            repayment_hierarchy=home_loan_redraw.REPAYMENT_HIERARCHY,
            overpayment_features=[mock_overpayment_feature],
        )
        mock_does_repayment_fully_repay_loan.assert_called_once_with(
            repayment_posting_instructions=mock_posting_instructions,
            balances=sentinel.balances_dummy_balances_observation,
            denomination=self.default_denomination,
            account_id=self.account_id,
        )
        expected_result = PostPostingHookResult(
            account_notification_directives=[
                AccountNotificationDirective(
                    notification_type="HOME_LOAN_REDRAW_PAID_OFF",
                    notification_details={"account_id": self.account_id},
                )
            ],
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=mock_posting_instructions,  # type: ignore
                    client_batch_id=f"{DEFAULT_HOOK_EXECUTION_ID}",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
        )
        self.assertEqual(post_posting_result, expected_result)

    @patch.object(home_loan_redraw.utils, "create_postings")
    def test_post_posting_withdrawal_returns_correct_posting_directives(
        self,
        mock_create_postings: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # setup postings
        postings_amount = Decimal(15.00)
        posting_instructions = [self.outbound_hard_settlement(amount=postings_amount)]

        # setup mocks
        mock_vault = self.create_mock(
            account_id=self.account_id,
            balances_observation_fetchers_mapping={
                home_loan_redraw.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
            }
        )
        mock_withdrawal_postings: list[Posting] = [
            Posting(
                credit=True,
                amount=Decimal(1),
                denomination=self.default_denomination,
                account_id=self.account_id,
                account_address="REDRAW",
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
            Posting(
                credit=False,
                amount=Decimal(1),
                denomination=self.default_denomination,
                account_id=self.account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
        ]
        mock_create_postings.return_value = mock_withdrawal_postings

        hook_args = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=posting_instructions,
            client_transactions={},
        )
        post_posting_result = home_loan_redraw.post_posting_hook(
            vault=mock_vault, hook_arguments=hook_args
        )

        # assertions
        mock_get_parameter.assert_called_once_with(vault=mock_vault, name="denomination")
        mock_create_postings.assert_called_once_with(
            debit_account=self.account_id,
            debit_address="REDRAW",
            denomination=self.default_denomination,
            amount=postings_amount,
            credit_account=self.account_id,
            credit_address=DEFAULT_ADDRESS,
        )

        expected_posting_instructions = [
            CustomInstruction(
                postings=mock_withdrawal_postings,
                instruction_details={
                    "description": "Redraw funds from the redraw account",
                    "event": "REDRAW_FUNDS_WITHDRAWAL",
                },
            )
        ]
        expected_result = PostPostingHookResult(
            account_notification_directives=[],
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_posting_instructions,  # type: ignore
                    client_batch_id=f"{DEFAULT_HOOK_EXECUTION_ID}",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
        )
        self.assertEqual(post_posting_result, expected_result)


class ConversionTest(HomeLoanRedrawTest):
    def test_conversion_passes_schedules_through(self):

        effective_datetime = DEFAULT_DATETIME
        existing_schedules: dict[str, ScheduledEvent] = {
            sentinel.accrual_event_type: SentinelScheduledEvent("accrual_event"),
            sentinel.application_event_type: SentinelScheduledEvent("application_event"),
        }

        hook_args = ConversionHookArguments(
            effective_datetime=effective_datetime, existing_schedules=existing_schedules
        )

        expected_result = ConversionHookResult(
            scheduled_events_return_value=existing_schedules,
            posting_instructions_directives=[],
        )

        hook_result = home_loan_redraw.conversion_hook(
            vault=sentinel.vault, hook_arguments=hook_args
        )

        self.assertEqual(hook_result, expected_result)
