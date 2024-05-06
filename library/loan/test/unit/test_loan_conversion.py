# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# library
from library.loan.contracts.template import loan
from library.loan.test.unit.test_loan_common import LoanTestBase

# features
import library.features.v4.lending.lending_addresses as lending_addresses
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    BalanceDefaultDict,
    BalancesObservation,
    ConversionHookArguments,
    CustomInstruction as _CustomInstruction,
    ParameterTimeseries,
    Phase,
    Posting,
    ScheduledEvent,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    ACCOUNT_ID,
    DEFAULT_DATETIME,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    ConversionHookResult,
    CustomInstruction,
    PostingInstructionsDirective,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    DEFAULT_POSTINGS,
    SentinelCustomInstruction,
    SentinelScheduledEvent,
)


@patch.object(loan, "_get_amortisation_feature")
@patch.object(loan, "_get_interest_rate_feature")
@patch.object(loan.emi, "amortise")
@patch.object(loan.utils, "get_parameter")
@patch.object(loan.disbursement, "get_disbursement_custom_instruction")
@patch.object(loan.disbursement, "get_deposit_account_parameter")
@patch.object(loan.close_loan, "net_balances")
class ConversionTestWithTopUp(LoanTestBase):
    # Real balances needed as they are used to create inflight balances
    common_balances = {
        loan.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: BalancesObservation(
            balances=BalanceDefaultDict(), value_datetime=DEFAULT_DATETIME
        )
    }
    # Real CIs are needed as they are used to create inflight balances
    tracker_updates_ci = _CustomInstruction(
        postings=[
            Posting(
                credit=True,
                amount=Decimal("1"),
                denomination=sentinel.denomination,
                account_id=ACCOUNT_ID,
                account_address=lending_addresses.EMI,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
            Posting(
                credit=False,
                amount=Decimal("1"),
                denomination=sentinel.denomination,
                account_id=ACCOUNT_ID,
                account_address=lending_addresses.INTERNAL_CONTRA,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
        ]
    )
    disbursement_ci = _CustomInstruction(
        postings=[
            Posting(
                credit=True,
                amount=Decimal("1"),
                denomination=sentinel.denomination,
                account_id=sentinel.deposit_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
            Posting(
                credit=False,
                amount=Decimal("1"),
                denomination=sentinel.denomination,
                account_id=ACCOUNT_ID,
                account_address=lending_addresses.PRINCIPAL,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
        ]
    )
    reamortisation_instruction = SentinelCustomInstruction("reamortise")
    existing_schedules: dict[str, ScheduledEvent] = {
        sentinel.some_event: SentinelScheduledEvent("some_event"),
        sentinel.some_other_event: SentinelScheduledEvent("some_other_event"),
    }
    common_params = {
        "denomination": sentinel.denomination,
        "top_up": "true",
        "interest_accrual_rest_type": "daily",
        "amortisation_method": "declining principal",
    }

    def test_loan_top_up(
        self,
        mock_net_balances: MagicMock,
        mock_get_deposit_account_parameter: MagicMock,
        mock_get_disbursement_custom_instruction: MagicMock,
        mock_get_parameter: MagicMock,
        mock_amortise: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_get_amortisation_feature: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_params)
        mock_get_interest_rate_feature.return_value = sentinel.interest_rate_feature
        mock_get_amortisation_feature.return_value = sentinel.amortisation_feature
        mock_get_deposit_account_parameter.return_value = sentinel.deposit_account_id
        mock_amortise.return_value = [self.reamortisation_instruction]
        mock_get_disbursement_custom_instruction.return_value = [self.disbursement_ci]

        mock_net_balances.return_value = [self.tracker_updates_ci]

        parameter_timeseries = ParameterTimeseries(
            iterable=[
                (DEFAULT_DATETIME - relativedelta(seconds=1), Decimal("1000")),
                (DEFAULT_DATETIME, Decimal("2500")),
            ]
        )
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.common_balances,
            parameter_ts={"principal": parameter_timeseries},
        )

        expected_result = ConversionHookResult(
            scheduled_events_return_value=self.existing_schedules,
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[
                        self.tracker_updates_ci,
                        self.disbursement_ci,
                        self.reamortisation_instruction,
                    ],
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
        )

        hook_args = ConversionHookArguments(
            effective_datetime=DEFAULT_DATETIME, existing_schedules=self.existing_schedules
        )

        hook_result = loan.conversion_hook(vault=mock_vault, hook_arguments=hook_args)

        self.assertEqual(hook_result, expected_result)
        mock_net_balances.assert_called_once_with(
            balances={},
            denomination=sentinel.denomination,
            account_id=ACCOUNT_ID,
            residual_cleanup_features=[
                loan.overpayment.OverpaymentResidualCleanupFeature,
                loan.lending_interfaces.ResidualCleanup(
                    get_residual_cleanup_postings=loan._get_residual_cleanup_postings
                ),
            ],
        )
        mock_get_disbursement_custom_instruction.assert_called_once_with(
            account_id=ACCOUNT_ID,
            deposit_account_id=sentinel.deposit_account_id,
            principal=Decimal("1500"),
            denomination=sentinel.denomination,
        )
        mock_get_deposit_account_parameter.assert_called_once_with(vault=mock_vault)
        mock_amortise.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=sentinel.amortisation_feature,
            principal_amount=Decimal("1"),
            interest_calculation_feature=sentinel.interest_rate_feature,
            event="LOAN_TOP_UP",
        )

    @patch.object(loan.utils, "create_postings")
    def test_loan_top_up_monthly_rest(
        self,
        mock_create_postings: MagicMock,
        mock_net_balances: MagicMock,
        mock_get_deposit_account_parameter: MagicMock,
        mock_get_disbursement_custom_instruction: MagicMock,
        mock_get_parameter: MagicMock,
        mock_amortise: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_get_amortisation_feature: MagicMock,
    ):
        mock_create_postings.return_value = DEFAULT_POSTINGS
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                **self.common_params,
                "interest_accrual_rest_type": "monthly",
            }
        )
        mock_get_interest_rate_feature.return_value = sentinel.interest_rate_feature
        mock_get_amortisation_feature.return_value = sentinel.amortisation_feature
        mock_get_deposit_account_parameter.return_value = sentinel.deposit_account_id
        mock_amortise.return_value = [self.reamortisation_instruction]
        mock_get_disbursement_custom_instruction.return_value = [self.disbursement_ci]
        expected_principal_at_cycle_start_ci = CustomInstruction(
            postings=DEFAULT_POSTINGS,
            override_all_restrictions=True,
            instruction_details={
                "description": "Update principal at repayment cycle start balance",
                "event": loan.LOAN_TOP_UP,
            },
        )
        mock_net_balances.return_value = [self.tracker_updates_ci]

        parameter_timeseries = ParameterTimeseries(
            iterable=[
                (DEFAULT_DATETIME - relativedelta(seconds=1), Decimal("1000")),
                (DEFAULT_DATETIME, Decimal("2500")),
            ]
        )
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.common_balances,
            parameter_ts={"principal": parameter_timeseries},
        )

        expected_result = ConversionHookResult(
            scheduled_events_return_value=self.existing_schedules,
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[
                        self.tracker_updates_ci,
                        self.disbursement_ci,
                        self.reamortisation_instruction,
                        expected_principal_at_cycle_start_ci,
                    ],
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
        )
        hook_args = ConversionHookArguments(
            effective_datetime=DEFAULT_DATETIME, existing_schedules=self.existing_schedules
        )
        hook_result = loan.conversion_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertEqual(hook_result, expected_result)
        mock_net_balances.assert_called_once_with(
            balances={},
            denomination=sentinel.denomination,
            account_id=ACCOUNT_ID,
            residual_cleanup_features=[
                loan.overpayment.OverpaymentResidualCleanupFeature,
                loan.lending_interfaces.ResidualCleanup(
                    get_residual_cleanup_postings=loan._get_residual_cleanup_postings
                ),
            ],
        )
        mock_get_disbursement_custom_instruction.assert_called_once_with(
            account_id=ACCOUNT_ID,
            deposit_account_id=sentinel.deposit_account_id,
            principal=Decimal("1500"),
            denomination=sentinel.denomination,
        )
        mock_get_deposit_account_parameter.assert_called_once_with(vault=mock_vault)
        mock_amortise.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=sentinel.amortisation_feature,
            principal_amount=Decimal("1"),
            interest_calculation_feature=sentinel.interest_rate_feature,
            event="LOAN_TOP_UP",
        )
        mock_create_postings.assert_called_once_with(
            amount=Decimal("1"),
            debit_account=ACCOUNT_ID,
            credit_account=ACCOUNT_ID,
            debit_address="MONTHLY_REST_EFFECTIVE_PRINCIPAL",
            credit_address="INTERNAL_CONTRA",
            denomination=sentinel.denomination,
        )

    @patch.object(loan.balloon_payments, "update_no_repayment_balloon_schedule")
    @patch.object(loan.utils, "create_postings")
    def test_loan_top_up_monthly_rest_no_repayment(
        self,
        mock_create_postings: MagicMock,
        mock_no_repayment_balloon_schedule: MagicMock,
        mock_net_balances: MagicMock,
        mock_get_deposit_account_parameter: MagicMock,
        mock_get_disbursement_custom_instruction: MagicMock,
        mock_get_parameter: MagicMock,
        mock_amortise: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_get_amortisation_feature: MagicMock,
    ):
        mock_create_postings.return_value = DEFAULT_POSTINGS
        test_schedules = self.existing_schedules.copy()
        test_schedules[sentinel.balloon_event] = SentinelScheduledEvent("original_balloon_event")
        expected_schedules = test_schedules.copy()
        expected_schedules[sentinel.balloon_event] = SentinelScheduledEvent("updated_balloon_event")
        common_params = self.common_params.copy()
        common_params["amortisation_method"] = loan.no_repayment.AMORTISATION_METHOD
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                **common_params,
                "interest_accrual_rest_type": "monthly",
                "balloon_payment_days_delta": 0,
                "total_repayment_count": 24,
            }
        )
        mock_get_interest_rate_feature.return_value = sentinel.interest_rate_feature
        mock_get_amortisation_feature.return_value = sentinel.amortisation_feature
        mock_get_deposit_account_parameter.return_value = sentinel.deposit_account_id
        mock_amortise.return_value = [self.reamortisation_instruction]
        mock_get_disbursement_custom_instruction.return_value = [self.disbursement_ci]
        expected_principal_at_cycle_start_ci = CustomInstruction(
            postings=DEFAULT_POSTINGS,
            override_all_restrictions=True,
            instruction_details={
                "description": "Update principal at repayment cycle start balance",
                "event": loan.LOAN_TOP_UP,
            },
        )
        mock_net_balances.return_value = [self.tracker_updates_ci]
        mock_no_repayment_balloon_schedule.return_value = {
            sentinel.balloon_event: SentinelScheduledEvent("updated_balloon_event"),
        }

        principal_timeseries = ParameterTimeseries(
            iterable=[
                (DEFAULT_DATETIME - relativedelta(seconds=1), Decimal("1000")),
                (DEFAULT_DATETIME, Decimal("2500")),
            ]
        )
        term_timeseries = ParameterTimeseries(
            iterable=[
                (DEFAULT_DATETIME - relativedelta(seconds=1), Decimal("12")),
                (DEFAULT_DATETIME, Decimal("24")),
            ]
        )
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.common_balances,
            parameter_ts={
                "principal": principal_timeseries,
                "total_repayment_count": term_timeseries,
            },
        )

        expected_result = ConversionHookResult(
            scheduled_events_return_value=expected_schedules,
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[
                        self.tracker_updates_ci,
                        self.disbursement_ci,
                        self.reamortisation_instruction,
                        expected_principal_at_cycle_start_ci,
                    ],
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
        )

        hook_args = ConversionHookArguments(
            effective_datetime=DEFAULT_DATETIME, existing_schedules=test_schedules
        )

        hook_result = loan.conversion_hook(vault=mock_vault, hook_arguments=hook_args)

        self.assertEqual(hook_result, expected_result)
        mock_net_balances.assert_called_once_with(
            balances={},
            denomination=sentinel.denomination,
            account_id=ACCOUNT_ID,
            residual_cleanup_features=[
                loan.overpayment.OverpaymentResidualCleanupFeature,
                loan.lending_interfaces.ResidualCleanup(
                    get_residual_cleanup_postings=loan._get_residual_cleanup_postings
                ),
            ],
        )
        mock_get_disbursement_custom_instruction.assert_called_once_with(
            account_id=ACCOUNT_ID,
            deposit_account_id=sentinel.deposit_account_id,
            principal=Decimal("1500"),
            denomination=sentinel.denomination,
        )
        mock_get_deposit_account_parameter.assert_called_once_with(vault=mock_vault)
        mock_amortise.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=sentinel.amortisation_feature,
            principal_amount=Decimal("1"),
            interest_calculation_feature=sentinel.interest_rate_feature,
            event="LOAN_TOP_UP",
        )
        mock_create_postings.assert_called_once_with(
            amount=Decimal("1"),
            debit_account=ACCOUNT_ID,
            credit_account=ACCOUNT_ID,
            debit_address="MONTHLY_REST_EFFECTIVE_PRINCIPAL",
            credit_address="INTERNAL_CONTRA",
            denomination=sentinel.denomination,
        )

    def test_loan_top_up_principal_parameter_not_updated(
        self,
        mock_net_balances: MagicMock,
        mock_get_deposit_account_parameter: MagicMock,
        mock_get_disbursement_custom_instruction: MagicMock,
        mock_get_parameter: MagicMock,
        mock_amortise: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_get_amortisation_feature: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_params)
        mock_get_interest_rate_feature.return_value = sentinel.interest_rate_feature
        mock_get_amortisation_feature.return_value = sentinel.amortisation_feature
        mock_amortise.return_value = [self.reamortisation_instruction]

        mock_net_balances.return_value = [self.tracker_updates_ci]

        parameter_timeseries = ParameterTimeseries(
            iterable=[(DEFAULT_DATETIME - relativedelta(seconds=1), Decimal("1000"))]
        )
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.common_balances,
            parameter_ts={"principal": parameter_timeseries},
        )

        expected_result = ConversionHookResult(
            scheduled_events_return_value=self.existing_schedules,
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[
                        self.tracker_updates_ci,
                        self.reamortisation_instruction,
                    ],
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
        )

        hook_args = ConversionHookArguments(
            effective_datetime=DEFAULT_DATETIME, existing_schedules=self.existing_schedules
        )

        hook_result = loan.conversion_hook(vault=mock_vault, hook_arguments=hook_args)

        self.assertEqual(hook_result, expected_result)
        mock_net_balances.assert_called_once_with(
            balances={},
            denomination=sentinel.denomination,
            account_id=ACCOUNT_ID,
            residual_cleanup_features=[
                loan.overpayment.OverpaymentResidualCleanupFeature,
                loan.lending_interfaces.ResidualCleanup(
                    get_residual_cleanup_postings=loan._get_residual_cleanup_postings
                ),
            ],
        )
        mock_get_disbursement_custom_instruction.assert_not_called()
        mock_get_deposit_account_parameter.assert_not_called()
        mock_amortise.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=sentinel.amortisation_feature,
            principal_amount=Decimal("0"),
            interest_calculation_feature=sentinel.interest_rate_feature,
            event="LOAN_TOP_UP",
        )

    def test_loan_top_up_principal_parameter_delta_negative(
        self,
        mock_net_balances: MagicMock,
        mock_get_deposit_account_parameter: MagicMock,
        mock_get_disbursement_custom_instruction: MagicMock,
        mock_get_parameter: MagicMock,
        mock_amortise: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_get_amortisation_feature: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_params)
        mock_get_interest_rate_feature.return_value = sentinel.interest_rate_feature
        mock_get_amortisation_feature.return_value = sentinel.amortisation_feature
        mock_amortise.return_value = [self.reamortisation_instruction]

        mock_net_balances.return_value = [self.tracker_updates_ci]

        parameter_timeseries = ParameterTimeseries(
            iterable=[
                (DEFAULT_DATETIME - relativedelta(seconds=1), Decimal("1000")),
                (DEFAULT_DATETIME, Decimal("900")),
            ]
        )
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.common_balances,
            parameter_ts={"principal": parameter_timeseries},
        )

        expected_result = ConversionHookResult(
            scheduled_events_return_value=self.existing_schedules,
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[
                        self.tracker_updates_ci,
                        self.reamortisation_instruction,
                    ],
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
        )

        hook_args = ConversionHookArguments(
            effective_datetime=DEFAULT_DATETIME, existing_schedules=self.existing_schedules
        )

        hook_result = loan.conversion_hook(vault=mock_vault, hook_arguments=hook_args)

        self.assertEqual(hook_result, expected_result)
        mock_net_balances.assert_called_once_with(
            balances={},
            denomination=sentinel.denomination,
            account_id=ACCOUNT_ID,
            residual_cleanup_features=[
                loan.overpayment.OverpaymentResidualCleanupFeature,
                loan.lending_interfaces.ResidualCleanup(
                    get_residual_cleanup_postings=loan._get_residual_cleanup_postings
                ),
            ],
        )
        mock_get_disbursement_custom_instruction.assert_not_called()
        mock_get_deposit_account_parameter.assert_not_called()
        mock_amortise.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=sentinel.amortisation_feature,
            principal_amount=Decimal("0"),
            interest_calculation_feature=sentinel.interest_rate_feature,
            event="LOAN_TOP_UP",
        )

    def test_loan_top_up_principal_parameter_delta_zero(
        self,
        mock_net_balances: MagicMock,
        mock_get_deposit_account_parameter: MagicMock,
        mock_get_disbursement_custom_instruction: MagicMock,
        mock_get_parameter: MagicMock,
        mock_amortise: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_get_amortisation_feature: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_params)
        mock_get_interest_rate_feature.return_value = sentinel.interest_rate_feature
        mock_get_amortisation_feature.return_value = sentinel.amortisation_feature
        mock_amortise.return_value = [self.reamortisation_instruction]

        mock_net_balances.return_value = [self.tracker_updates_ci]

        parameter_timeseries = ParameterTimeseries(
            iterable=[
                (DEFAULT_DATETIME - relativedelta(seconds=1), Decimal("1000")),
                (DEFAULT_DATETIME, Decimal("1000")),
            ]
        )
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.common_balances,
            parameter_ts={"principal": parameter_timeseries},
        )

        expected_result = ConversionHookResult(
            scheduled_events_return_value=self.existing_schedules,
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[
                        self.tracker_updates_ci,
                        self.reamortisation_instruction,
                    ],
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
        )

        hook_args = ConversionHookArguments(
            effective_datetime=DEFAULT_DATETIME, existing_schedules=self.existing_schedules
        )

        hook_result = loan.conversion_hook(vault=mock_vault, hook_arguments=hook_args)

        self.assertEqual(hook_result, expected_result)
        mock_net_balances.assert_called_once_with(
            balances={},
            denomination=sentinel.denomination,
            account_id=ACCOUNT_ID,
            residual_cleanup_features=[
                loan.overpayment.OverpaymentResidualCleanupFeature,
                loan.lending_interfaces.ResidualCleanup(
                    get_residual_cleanup_postings=loan._get_residual_cleanup_postings
                ),
            ],
        )
        mock_get_disbursement_custom_instruction.assert_not_called()
        mock_get_deposit_account_parameter.assert_not_called()
        mock_amortise.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=sentinel.amortisation_feature,
            principal_amount=Decimal("0"),
            interest_calculation_feature=sentinel.interest_rate_feature,
            event="LOAN_TOP_UP",
        )


@patch.object(loan.utils, "get_parameter")
class ConversionTestWithoutTopUp(LoanTestBase):
    def test_loan_top_up_parameter_not_true(self, mock_get_parameter: MagicMock):
        mock_get_parameter.return_value = False
        existing_schedules: dict[str, ScheduledEvent] = {
            sentinel.some_event: SentinelScheduledEvent("some_event"),
            sentinel.some_other_event: SentinelScheduledEvent("some_other_event"),
        }

        expected_result = ConversionHookResult(
            scheduled_events_return_value=existing_schedules,
            posting_instructions_directives=[],
        )

        hook_args = ConversionHookArguments(
            effective_datetime=DEFAULT_DATETIME, existing_schedules=existing_schedules
        )

        hook_result = loan.conversion_hook(vault=sentinel.vault, hook_arguments=hook_args)

        self.assertEqual(hook_result, expected_result)
