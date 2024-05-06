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
from contracts_api import (
    DEFAULT_ASSET,
    Balance,
    BalanceCoordinate,
    BalanceDefaultDict,
    BalancesObservation,
    ConversionHookArguments,
    CustomInstruction,
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
    PostingInstructionsDirective,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelCustomInstruction,
    SentinelScheduledEvent,
)


class ConversionTest(MortgageTestBase):

    common_params = {
        "denomination": sentinel.denomination,
        mortgage.PARAM_PRODUCT_SWITCH: True,
        mortgage.PARAM_INTEREST_ONLY_TERM: 0,
    }
    # Real balances needed as they are used to create inflight balances
    common_balances = {
        mortgage.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: BalancesObservation(
            balances=BalanceDefaultDict(), value_datetime=DEFAULT_DATETIME
        )
    }
    allowance_fee = SentinelCustomInstruction("allowance_fee")
    # Real CIs are needed as they are used to create inflight balances
    tracker_updates = CustomInstruction(
        postings=[
            Posting(
                credit=True,
                amount=Decimal("1"),
                denomination=sentinel.denomination,
                account_id=ACCOUNT_ID,
                account_address=mortgage.lending_addresses.EMI,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
            Posting(
                credit=False,
                amount=Decimal("1"),
                denomination=sentinel.denomination,
                account_id=ACCOUNT_ID,
                account_address=mortgage.lending_addresses.INTERNAL_CONTRA,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
        ]
    )
    reamortisation_instruction = SentinelCustomInstruction("reamortise")

    @patch.object(mortgage.utils, "get_parameter")
    @patch.object(mortgage.utils, "balance_at_coordinates")
    @patch.object(mortgage.emi, "amortise")
    @patch.object(mortgage.close_loan, "net_balances")
    @patch.object(mortgage.overpayment_allowance, "update_scheduled_event")
    @patch.object(mortgage.overpayment_allowance, "handle_allowance_usage_adhoc")
    def test_conversion_with_product_switch(
        self,
        mock_handle_overpayment_allowance_adhoc: MagicMock,
        mock_overpayment_allowance_update_scheduled_events: MagicMock,
        mock_net_balances: MagicMock,
        mock_amortise: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):

        effective_datetime = DEFAULT_DATETIME
        existing_schedules: dict[str, ScheduledEvent] = {
            sentinel.some_other_event_type: SentinelScheduledEvent("some_other_event"),
            sentinel.overpayment_allowance_event_type: SentinelScheduledEvent(
                "original_overpayment_allowance_event"
            ),
        }
        mock_handle_overpayment_allowance_adhoc.return_value = [ConversionTest.allowance_fee]
        mock_net_balances.return_value = [ConversionTest.tracker_updates]
        mock_balance_at_coordinates.return_value = sentinel.current_principal
        mock_amortise.return_value = [ConversionTest.reamortisation_instruction]
        mock_overpayment_allowance_update_scheduled_events.return_value = {
            sentinel.overpayment_allowance_event_type: SentinelScheduledEvent(
                "new_overpayment_allowance_event"
            )
        }

        expected_result = ConversionHookResult(
            scheduled_events_return_value={
                sentinel.some_other_event_type: SentinelScheduledEvent("some_other_event"),
                sentinel.overpayment_allowance_event_type: SentinelScheduledEvent(
                    "new_overpayment_allowance_event"
                ),
            },
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[
                        # Order is important as reamortisation must happen after tracker updates
                        ConversionTest.tracker_updates,
                        ConversionTest.reamortisation_instruction,
                        ConversionTest.allowance_fee,
                    ],
                    value_datetime=effective_datetime,
                )
            ],
        )

        mock_get_parameter.side_effect = mock_utils_get_parameter(ConversionTest.common_params)
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=ConversionTest.common_balances
        )
        hook_args = ConversionHookArguments(
            effective_datetime=effective_datetime, existing_schedules=existing_schedules
        )

        hook_result = mortgage.conversion_hook(vault=mock_vault, hook_arguments=hook_args)

        self.assertEqual(hook_result, expected_result)

        mock_net_balances.assert_called_once_with(
            balances=BalanceDefaultDict(),
            denomination=sentinel.denomination,
            account_id=mock_vault.account_id,
            residual_cleanup_features=[
                mortgage.overpayment.OverpaymentResidualCleanupFeature,
                mortgage.overpayment_allowance.OverpaymentAllowanceResidualCleanupFeature,
                mortgage.due_amount_calculation.DueAmountCalculationResidualCleanupFeature,
                mortgage.lending_interfaces.ResidualCleanup(
                    get_residual_cleanup_postings=mortgage._get_residual_cleanup_postings
                ),
            ],
        )
        mock_amortise.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=effective_datetime,
            amortisation_feature=mortgage.declining_principal.AmortisationFeature,
            principal_amount=sentinel.current_principal,
            interest_calculation_feature=mortgage.fixed_to_variable.InterestRate,
            balances=BalanceDefaultDict(
                # this is the observation + the tracker posting balances
                mapping={
                    BalanceCoordinate(
                        denomination=sentinel.denomination,
                        account_address=mortgage.lending_addresses.EMI,
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ): Balance(net=Decimal("-1"), debit=Decimal("0"), credit=Decimal("1")),
                    BalanceCoordinate(
                        denomination=sentinel.denomination,
                        account_address=mortgage.lending_addresses.INTERNAL_CONTRA,
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ): Balance(net=Decimal("1"), debit=Decimal("1"), credit=Decimal("0")),
                }
            ),
            event="PRODUCT_SWITCH",
        )
        mock_handle_overpayment_allowance_adhoc.assert_called_once_with(
            vault=mock_vault,
            account_type=mortgage.ACCOUNT_TYPE,
            effective_datetime=effective_datetime,
        )
        mock_overpayment_allowance_update_scheduled_events.assert_called_once_with(
            vault=mock_vault, effective_datetime=effective_datetime
        )

    @patch.object(mortgage.utils, "get_parameter")
    @patch.object(mortgage.utils, "balance_at_coordinates")
    @patch.object(mortgage.emi, "amortise")
    @patch.object(mortgage.close_loan, "net_balances")
    @patch.object(mortgage.overpayment_allowance, "update_scheduled_event")
    @patch.object(mortgage.overpayment_allowance, "handle_allowance_usage_adhoc")
    def test_conversion_with_product_switch_no_reamortisation_during_interest_only_term(
        self,
        mock_handle_overpayment_allowance_adhoc: MagicMock,
        mock_overpayment_allowance_update_scheduled_events: MagicMock,
        mock_net_balances: MagicMock,
        mock_amortise: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        effective_datetime = DEFAULT_DATETIME
        existing_schedules: dict[str, ScheduledEvent] = {
            sentinel.some_other_event_type: SentinelScheduledEvent("some_other_event"),
            sentinel.overpayment_allowance_event_type: SentinelScheduledEvent(
                "original_overpayment_allowance_event"
            ),
        }
        mock_handle_overpayment_allowance_adhoc.return_value = [ConversionTest.allowance_fee]
        mock_net_balances.return_value = [ConversionTest.tracker_updates]
        mock_balance_at_coordinates.return_value = sentinel.current_principal
        mock_overpayment_allowance_update_scheduled_events.return_value = {
            sentinel.overpayment_allowance_event_type: SentinelScheduledEvent(
                "new_overpayment_allowance_event"
            )
        }
        # by setting interest only term to 1 we won't amortise
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {**ConversionTest.common_params, mortgage.PARAM_INTEREST_ONLY_TERM: 1}
        )

        expected_result = ConversionHookResult(
            scheduled_events_return_value={
                sentinel.some_other_event_type: SentinelScheduledEvent("some_other_event"),
                sentinel.overpayment_allowance_event_type: SentinelScheduledEvent(
                    "new_overpayment_allowance_event"
                ),
            },
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[
                        ConversionTest.tracker_updates,
                        ConversionTest.allowance_fee,
                    ],
                    value_datetime=effective_datetime,
                )
            ],
        )

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=ConversionTest.common_balances
        )
        hook_args = ConversionHookArguments(
            effective_datetime=effective_datetime, existing_schedules=existing_schedules
        )

        hook_result = mortgage.conversion_hook(vault=mock_vault, hook_arguments=hook_args)

        self.assertEqual(hook_result, expected_result)

        mock_net_balances.assert_called_once_with(
            balances=BalanceDefaultDict(),
            denomination=sentinel.denomination,
            account_id=mock_vault.account_id,
            residual_cleanup_features=[
                mortgage.overpayment.OverpaymentResidualCleanupFeature,
                mortgage.overpayment_allowance.OverpaymentAllowanceResidualCleanupFeature,
                mortgage.due_amount_calculation.DueAmountCalculationResidualCleanupFeature,
                mortgage.lending_interfaces.ResidualCleanup(
                    get_residual_cleanup_postings=mortgage._get_residual_cleanup_postings
                ),
            ],
        )
        mock_amortise.assert_not_called()
        mock_handle_overpayment_allowance_adhoc.assert_called_once_with(
            vault=mock_vault,
            account_type=mortgage.ACCOUNT_TYPE,
            effective_datetime=effective_datetime,
        )
        mock_overpayment_allowance_update_scheduled_events.assert_called_once_with(
            vault=mock_vault, effective_datetime=effective_datetime
        )

    @patch.object(mortgage.utils, "get_parameter")
    @patch.object(mortgage.emi, "amortise")
    @patch.object(mortgage.close_loan, "net_balances")
    @patch.object(mortgage.overpayment_allowance, "update_scheduled_event")
    @patch.object(mortgage.overpayment_allowance, "handle_allowance_usage_adhoc")
    def test_conversion_without_postings_still_updates_overpayment_allowance_schedule(
        self,
        mock_handle_overpayment_allowance_adhoc: MagicMock,
        mock_overpayment_allowance_update_scheduled_events: MagicMock,
        mock_net_balances: MagicMock,
        mock_amortise: MagicMock,
        mock_get_parameter: MagicMock,
    ):

        effective_datetime = DEFAULT_DATETIME
        existing_schedules: dict[str, ScheduledEvent] = {
            sentinel.some_other_event_type: SentinelScheduledEvent("some_other_event"),
            sentinel.overpayment_allowance_event_type: SentinelScheduledEvent(
                "original_overpayment_allowance_event"
            ),
        }
        mock_handle_overpayment_allowance_adhoc.return_value = []
        mock_net_balances.return_value = []
        mock_overpayment_allowance_update_scheduled_events.return_value = {
            sentinel.overpayment_allowance_event_type: SentinelScheduledEvent(
                "new_overpayment_allowance_event"
            )
        }
        # by setting interest only term to 1 we won't amortise
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {**ConversionTest.common_params, mortgage.PARAM_INTEREST_ONLY_TERM: 1}
        )

        expected_result = ConversionHookResult(
            scheduled_events_return_value={
                sentinel.some_other_event_type: SentinelScheduledEvent("some_other_event"),
                sentinel.overpayment_allowance_event_type: SentinelScheduledEvent(
                    "new_overpayment_allowance_event"
                ),
            },
            posting_instructions_directives=[],
        )

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=ConversionTest.common_balances
        )

        hook_args = ConversionHookArguments(
            effective_datetime=effective_datetime, existing_schedules=existing_schedules
        )

        hook_result = mortgage.conversion_hook(vault=mock_vault, hook_arguments=hook_args)

        self.assertEqual(hook_result, expected_result)

        mock_net_balances.assert_called_once_with(
            balances=BalanceDefaultDict(),
            denomination=sentinel.denomination,
            account_id=mock_vault.account_id,
            residual_cleanup_features=[
                mortgage.overpayment.OverpaymentResidualCleanupFeature,
                mortgage.overpayment_allowance.OverpaymentAllowanceResidualCleanupFeature,
                mortgage.due_amount_calculation.DueAmountCalculationResidualCleanupFeature,
                mortgage.lending_interfaces.ResidualCleanup(
                    get_residual_cleanup_postings=mortgage._get_residual_cleanup_postings
                ),
            ],
        )
        mock_amortise.assert_not_called()
        mock_handle_overpayment_allowance_adhoc.assert_called_once_with(
            vault=mock_vault,
            account_type=mortgage.ACCOUNT_TYPE,
            effective_datetime=effective_datetime,
        )
        mock_overpayment_allowance_update_scheduled_events.assert_called_once_with(
            vault=mock_vault, effective_datetime=effective_datetime
        )

    @patch.object(mortgage.utils, "get_parameter")
    @patch.object(mortgage.emi, "amortise")
    @patch.object(mortgage.close_loan, "net_balances")
    @patch.object(mortgage.overpayment_allowance, "update_scheduled_event")
    @patch.object(mortgage.overpayment_allowance, "handle_allowance_usage_adhoc")
    def test_conversion_without_product_switch_passes_schedules_through(
        self,
        mock_handle_overpayment_allowance_adhoc: MagicMock,
        mock_overpayment_allowance_update_scheduled_events: MagicMock,
        mock_net_balances: MagicMock,
        mock_amortise: MagicMock,
        mock_get_parameter: MagicMock,
    ):

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {mortgage.PARAM_PRODUCT_SWITCH: False}
        )

        effective_datetime = DEFAULT_DATETIME
        existing_schedules: dict[str, ScheduledEvent] = {
            sentinel.some_other_event_type: SentinelScheduledEvent("some_other_event"),
            sentinel.overpayment_allowance_event_type: SentinelScheduledEvent(
                "original_overpayment_allowance_event"
            ),
        }

        expected_result = ConversionHookResult(
            scheduled_events_return_value=existing_schedules,
            posting_instructions_directives=[],
        )

        hook_args = ConversionHookArguments(
            effective_datetime=effective_datetime, existing_schedules=existing_schedules
        )

        hook_result = mortgage.conversion_hook(vault=sentinel.vault, hook_arguments=hook_args)

        self.assertEqual(hook_result, expected_result)

        mock_net_balances.assert_not_called()
        mock_amortise.assert_not_called()
        mock_handle_overpayment_allowance_adhoc.assert_not_called()
        mock_overpayment_allowance_update_scheduled_events.assert_not_called()
