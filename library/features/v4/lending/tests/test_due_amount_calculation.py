# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.v4.lending.due_amount_calculation as due_amount_calculation
import library.features.v4.lending.lending_interfaces as lending_interfaces
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import (
    DEFAULT_ASSET,
    Balance,
    BalanceCoordinate,
    BalanceDefaultDict,
    BalancesObservation,
    Phase,
    ScheduledEventHookArguments,
    SupervisorScheduledEventHookArguments,
    Tside,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    ACCOUNT_ID,
    DEFAULT_DATETIME,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    CustomInstruction,
    ParameterTimeseries,
    Posting,
    Rejection,
    RejectionReason,
    SmartContractEventType,
    SupervisorContractEventType,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelPosting,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.supervisor.common import (
    SupervisorFeatureTest,
)


class DueAmountCalculationTest(FeatureTest):
    maxDiff = None

    balances = BalanceDefaultDict(
        mapping={
            BalanceCoordinate(
                due_amount_calculation.lending_addresses.PRINCIPAL,
                DEFAULT_ASSET,
                sentinel.denomination,
                Phase.COMMITTED,
            ): Balance(net=sentinel.principal_net),
            BalanceCoordinate(
                due_amount_calculation.lending_addresses.EMI,
                DEFAULT_ASSET,
                sentinel.denomination,
                Phase.COMMITTED,
            ): Balance(net=sentinel.emi_net),
        }
    )


class SupervisorDueAmountCalculationTest(SupervisorFeatureTest):
    maxDiff = None

    balances = BalanceDefaultDict(
        mapping={
            BalanceCoordinate(
                due_amount_calculation.lending_addresses.PRINCIPAL,
                DEFAULT_ASSET,
                sentinel.denomination,
                Phase.COMMITTED,
            ): Balance(net=sentinel.principal_net),
            BalanceCoordinate(
                due_amount_calculation.lending_addresses.EMI,
                DEFAULT_ASSET,
                sentinel.denomination,
                Phase.COMMITTED,
            ): Balance(net=sentinel.emi_net),
        }
    )


class CalculateDuePrincipalTest(DueAmountCalculationTest):
    def test_calculate_principal_with_remaining_principal_gt_emi_minus_interest(self):
        due_principal = due_amount_calculation.calculate_due_principal(
            remaining_principal=Decimal("100"),
            emi_interest_to_apply=Decimal("1"),
            emi=Decimal("100"),
            is_final_due_event=False,
        )
        self.assertEqual(due_principal, Decimal("99"))

    def test_calculate_principal_with_remaining_principal_gt_emi_minus_interest_final_event(self):
        due_principal = due_amount_calculation.calculate_due_principal(
            remaining_principal=Decimal("100"),
            emi_interest_to_apply=Decimal("1"),
            emi=Decimal("100"),
            is_final_due_event=True,
        )
        self.assertEqual(due_principal, Decimal("100"))

    def test_calculate_principal_with_remaining_principal_eq_emi_minus_interest(self):
        due_principal = due_amount_calculation.calculate_due_principal(
            remaining_principal=Decimal("101"),
            emi_interest_to_apply=Decimal("1"),
            emi=Decimal("102"),
            is_final_due_event=False,
        )
        self.assertEqual(due_principal, Decimal("101"))

    def test_calculate_principal_with_remaining_principal_lt_emi_minus_interest(self):
        # can't exceed remaining principal
        due_principal = due_amount_calculation.calculate_due_principal(
            remaining_principal=Decimal("100"),
            emi_interest_to_apply=Decimal("1"),
            emi=Decimal("200"),
            is_final_due_event=False,
        )
        self.assertEqual(due_principal, Decimal("100"))

    def test_calculate_principal_with_zero_emi(self):
        due_principal = due_amount_calculation.calculate_due_principal(
            remaining_principal=Decimal("100"),
            emi_interest_to_apply=Decimal("1"),
            emi=Decimal("0"),
            is_final_due_event=False,
        )
        self.assertEqual(due_principal, Decimal("0"))


class TransferPrincipalDueTest(DueAmountCalculationTest):
    def test_transfer_principal_due_for_zero_amount(self):
        self.assertListEqual(
            due_amount_calculation.transfer_principal_due(
                customer_account=sentinel.account,
                principal_due=Decimal("0"),
                denomination=sentinel.denomination,
            ),
            [],
        )

    def test_transfer_principal_due_for_negative_amount(self):
        self.assertListEqual(
            due_amount_calculation.transfer_principal_due(
                customer_account=sentinel.account,
                principal_due=Decimal("-1"),
                denomination=sentinel.denomination,
            ),
            [],
        )

    def test_transfer_principal_due(self):
        self.assertListEqual(
            due_amount_calculation.transfer_principal_due(
                customer_account=sentinel.account,
                principal_due=Decimal("1"),
                denomination=sentinel.denomination,
            ),
            [
                Posting(
                    credit=True,
                    amount=Decimal("1"),
                    account_id=sentinel.account,
                    account_address=due_amount_calculation.lending_addresses.PRINCIPAL,
                    asset=DEFAULT_ASSET,
                    denomination=sentinel.denomination,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    credit=False,
                    amount=Decimal("1"),
                    account_id=sentinel.account,
                    account_address=due_amount_calculation.lending_addresses.PRINCIPAL_DUE,
                    asset=DEFAULT_ASSET,
                    denomination=sentinel.denomination,
                    phase=Phase.COMMITTED,
                ),
            ],
        )


class BalanceHelperTest(DueAmountCalculationTest):
    def setUp(self) -> None:
        self.balances = BalanceDefaultDict(
            mapping={
                BalanceCoordinate(
                    due_amount_calculation.lending_addresses.PRINCIPAL,
                    DEFAULT_ASSET,
                    sentinel.denomination,
                    Phase.COMMITTED,
                ): Balance(net=sentinel.principal_net),
                BalanceCoordinate(
                    due_amount_calculation.lending_addresses.EMI,
                    DEFAULT_ASSET,
                    sentinel.denomination,
                    Phase.COMMITTED,
                ): Balance(net=sentinel.emi_net),
            }
        )
        return super().setUp()

    def test_get_principal(self):
        self.assertEqual(
            due_amount_calculation.get_principal(
                balances=self.balances, denomination=sentinel.denomination
            ),
            sentinel.principal_net,
        )

    def test_get_emi(self):
        self.assertEqual(
            due_amount_calculation.get_emi(
                balances=self.balances, denomination=sentinel.denomination
            ),
            sentinel.emi_net,
        )


class PreParameterChangeValidationTest(DueAmountCalculationTest):
    def test_validate_due_amount_calculation_day_change_returns_none_after_first_event(self):
        mock_vault = self.create_mock(
            last_execution_datetimes={
                due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: DEFAULT_DATETIME
            }
        )
        result = due_amount_calculation.validate_due_amount_calculation_day_change(mock_vault)
        self.assertIsNone(result)

    def test_validate_due_amount_calculation_day_change_raises_rejection_before_first_event(self):
        mock_vault = self.create_mock(
            last_execution_datetimes={due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: None}
        )
        expected = Rejection(
            message="It is not possible to change the monthly repayment "
            "day if the first repayment date has not passed.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        result = due_amount_calculation.validate_due_amount_calculation_day_change(mock_vault)
        self.assertEqual(result, expected)


sentinel_instruction_details = {"sentinel": "details"}  # TODO: sentinel-ize in the future


@patch.object(due_amount_calculation.utils, "standard_instruction_details")
@patch.object(due_amount_calculation.utils, "get_parameter")
@patch.object(due_amount_calculation, "get_principal", MagicMock(return_value=sentinel.principal))
@patch.object(due_amount_calculation, "get_emi", MagicMock(return_value=sentinel.emi))
@patch.object(due_amount_calculation, "update_due_amount_calculation_counter")
@patch.object(due_amount_calculation, "transfer_principal_due")
@patch.object(due_amount_calculation, "calculate_due_principal")
class ScheduleLogicTest(DueAmountCalculationTest):
    def test_scheduled_event_hook_with_fetched_data_args(
        self,
        mock_calculate_due_principal: MagicMock,
        mock_transfer_principal_due: MagicMock,
        mock_update_due_amount_calculation_counter: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock()
        counter_postings = [SentinelPosting("counter_posting")]
        mock_update_due_amount_calculation_counter.return_value = counter_postings
        due_postings = [SentinelPosting("principal_due")]
        mock_transfer_principal_due.return_value = due_postings
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )
        mock_calculate_due_principal.return_value = sentinel.principal_due
        mock_standard_instruction_details.return_value = sentinel_instruction_details
        mock_amortisation_feature = MagicMock(term_details=MagicMock(return_value=(0, 2)))

        self.assertListEqual(
            due_amount_calculation.schedule_logic(
                vault=mock_vault,
                hook_arguments=ScheduledEventHookArguments(
                    effective_datetime=DEFAULT_DATETIME,
                    event_type=sentinel.event_type,
                ),
                amortisation_feature=mock_amortisation_feature,
                account_type=sentinel.account_type,
                balances=sentinel.balances,
                denomination=sentinel.denomination,
            ),
            [
                CustomInstruction(
                    postings=due_postings + counter_postings,  # type: ignore
                    override_all_restrictions=True,
                    instruction_details=sentinel_instruction_details,
                )
            ],
        )

        mock_calculate_due_principal.assert_called_once_with(
            remaining_principal=sentinel.principal,
            emi_interest_to_apply=Decimal(0),
            emi=sentinel.emi,
            is_final_due_event=False,
        )
        mock_transfer_principal_due.assert_called_once_with(
            customer_account=mock_vault.account_id,
            principal_due=sentinel.principal_due,
            denomination=sentinel.denomination,
        )

    def test_scheduled_event_hook_no_interest_application_feature(
        self,
        mock_calculate_due_principal: MagicMock,
        mock_transfer_principal_due: MagicMock,
        mock_update_due_amount_calculation_counter: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                due_amount_calculation.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                    BalancesObservation(balances=self.balances, value_datetime=DEFAULT_DATETIME)
                )
            }
        )
        counter_postings = [SentinelPosting("counter_posting")]
        mock_update_due_amount_calculation_counter.return_value = counter_postings
        due_postings = [SentinelPosting("principal_due")]
        mock_transfer_principal_due.return_value = due_postings
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )
        mock_calculate_due_principal.return_value = sentinel.principal_due
        mock_standard_instruction_details.return_value = sentinel_instruction_details
        mock_amortisation_feature = MagicMock(term_details=MagicMock(return_value=(0, 2)))

        self.assertListEqual(
            due_amount_calculation.schedule_logic(
                vault=mock_vault,
                hook_arguments=ScheduledEventHookArguments(
                    effective_datetime=DEFAULT_DATETIME,
                    event_type=sentinel.event_type,
                ),
                account_type=sentinel.account_type,
                amortisation_feature=mock_amortisation_feature,
            ),
            [
                CustomInstruction(
                    postings=due_postings + counter_postings,  # type: ignore
                    override_all_restrictions=True,
                    instruction_details=sentinel_instruction_details,
                )
            ],
        )

        mock_calculate_due_principal.assert_called_once_with(
            remaining_principal=sentinel.principal,
            emi_interest_to_apply=Decimal(0),
            emi=sentinel.emi,
            is_final_due_event=False,
        )
        mock_transfer_principal_due.assert_called_once_with(
            customer_account=mock_vault.account_id,
            principal_due=sentinel.principal_due,
            denomination=sentinel.denomination,
        )

    def test_scheduled_event_hook_no_due_principal_or_interest(
        self,
        mock_calculate_due_principal: MagicMock,
        mock_transfer_principal_due: MagicMock,
        mock_update_due_amount_calculation_counter: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                due_amount_calculation.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                    BalancesObservation(balances=self.balances, value_datetime=DEFAULT_DATETIME)
                )
            }
        )
        mock_update_due_amount_calculation_counter.return_value = []
        mock_transfer_principal_due.return_value = []
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )
        mock_calculate_due_principal.return_value = sentinel.principal_due
        mock_standard_instruction_details.return_value = sentinel_instruction_details
        mock_amortisation_feature = MagicMock(term_details=MagicMock(return_value=(0, 2)))

        self.assertListEqual(
            due_amount_calculation.schedule_logic(
                vault=mock_vault,
                hook_arguments=ScheduledEventHookArguments(
                    effective_datetime=DEFAULT_DATETIME,
                    event_type=sentinel.event_type,
                ),
                account_type=sentinel.account_type,
                amortisation_feature=mock_amortisation_feature,
            ),
            [],
        )

        mock_calculate_due_principal.assert_called_once_with(
            remaining_principal=sentinel.principal,
            emi_interest_to_apply=Decimal(0),
            emi=sentinel.emi,
            is_final_due_event=False,
        )
        mock_transfer_principal_due.assert_called_once_with(
            customer_account=mock_vault.account_id,
            principal_due=sentinel.principal_due,
            denomination=sentinel.denomination,
        )

    def test_scheduled_event_hook_with_interest_and_principal_due(
        self,
        mock_calculate_due_principal: MagicMock,
        mock_transfer_principal_due: MagicMock,
        mock_update_due_amount_calculation_counter: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        principal_due_postings = [SentinelPosting("principal_due")]
        interest_due_postings = [SentinelPosting("interest_due")]
        counter_postings = [SentinelPosting("counter_posting")]

        mock_interest_amounts = lending_interfaces.InterestAmounts(
            emi_accrued=sentinel.emi_accrued,
            emi_rounded_accrued=sentinel.emi_rounded_accrued,
            non_emi_accrued=sentinel.non_emi_accrued,
            non_emi_rounded_accrued=Decimal("0.12"),
            total_rounded=Decimal("1.23"),
        )
        mock_interest_application_feature = MagicMock(
            get_interest_to_apply=MagicMock(return_value=mock_interest_amounts),
            apply_interest=MagicMock(return_value=interest_due_postings),
        )
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                due_amount_calculation.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                    BalancesObservation(balances=self.balances, value_datetime=DEFAULT_DATETIME)
                )
            }
        )
        mock_transfer_principal_due.return_value = principal_due_postings
        mock_update_due_amount_calculation_counter.return_value = counter_postings
        mock_amortisation_feature = MagicMock(term_details=MagicMock(return_value=(0, 2)))
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )
        mock_calculate_due_principal.return_value = sentinel.principal_due
        mock_standard_instruction_details.return_value = sentinel_instruction_details

        expected_postings = interest_due_postings + principal_due_postings + counter_postings
        self.assertListEqual(
            due_amount_calculation.schedule_logic(
                vault=mock_vault,
                hook_arguments=ScheduledEventHookArguments(
                    effective_datetime=DEFAULT_DATETIME,
                    event_type=sentinel.event_type,
                ),
                account_type=sentinel.account_type,
                amortisation_feature=mock_amortisation_feature,
                interest_application_feature=mock_interest_application_feature,
            ),
            [
                CustomInstruction(
                    postings=expected_postings,  # type: ignore
                    override_all_restrictions=True,
                    instruction_details=sentinel_instruction_details,
                )
            ],
        )

        mock_calculate_due_principal.assert_called_once_with(
            remaining_principal=sentinel.principal,
            emi_interest_to_apply=Decimal("1.11"),
            emi=sentinel.emi,
            is_final_due_event=False,
        )
        mock_transfer_principal_due.assert_called_once_with(
            customer_account=mock_vault.account_id,
            principal_due=sentinel.principal_due,
            denomination=sentinel.denomination,
        )

    @patch.object(due_amount_calculation.emi, "update_emi")
    def test_scheduled_event_hook_requires_reamortisation(
        self,
        mock_update_emi: MagicMock,
        mock_calculate_due_principal: MagicMock,
        mock_transfer_principal_due: MagicMock,
        mock_update_due_amount_calculation_counter: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        counter_postings = [SentinelPosting("counter_posting")]
        mock_update_due_amount_calculation_counter.return_value = counter_postings
        mock_transfer_principal_due.return_value = []
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )
        mock_calculate_due_principal.return_value = sentinel.principal_due

        mock_should_trigger_reamortisation = MagicMock(return_value=True)
        mock_reamortisation_condition_feature = MagicMock(
            should_trigger_reamortisation=mock_should_trigger_reamortisation
        )
        mock_calculate_emi = MagicMock(return_value=sentinel.updated_emi)
        mock_term_details = MagicMock(return_value=(sentinel.elapsed_term, sentinel.remaining_term))
        mock_amortisation_feature = MagicMock(
            calculate_emi=mock_calculate_emi, term_details=mock_term_details
        )
        emi_postings = [SentinelPosting("emi_postings")]
        mock_update_emi.return_value = emi_postings
        mock_standard_instruction_details.return_value = sentinel_instruction_details

        last_execution_datetime = DEFAULT_DATETIME - relativedelta(months=1)
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                due_amount_calculation.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                    BalancesObservation(balances=self.balances, value_datetime=DEFAULT_DATETIME)
                )
            },
            last_execution_datetimes={
                due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: last_execution_datetime
            },
        )

        expected_result = [
            CustomInstruction(
                postings=emi_postings + counter_postings,  # type: ignore
                override_all_restrictions=True,
                instruction_details=sentinel_instruction_details,
            )
        ]

        result = due_amount_calculation.schedule_logic(
            vault=mock_vault,
            hook_arguments=ScheduledEventHookArguments(
                effective_datetime=DEFAULT_DATETIME,
                event_type=sentinel.event_type,
            ),
            account_type=sentinel.account_type,
            reamortisation_condition_features=[mock_reamortisation_condition_feature],
            amortisation_feature=mock_amortisation_feature,
            interest_rate_feature=sentinel.interest_rate_feature,
            principal_adjustment_features=[sentinel.principal_adjustments],
        )

        self.assertListEqual(expected_result, result)
        mock_term_details.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            use_expected_term=True,
            interest_rate=sentinel.interest_rate_feature,
            balances=self.balances,
        )
        mock_update_emi.assert_called_once_with(
            account_id=ACCOUNT_ID,
            denomination=sentinel.denomination,
            current_emi=sentinel.emi,
            updated_emi=sentinel.updated_emi,
        )
        mock_should_trigger_reamortisation.assert_called_once_with(
            vault=mock_vault,
            period_start_datetime=last_execution_datetime,
            period_end_datetime=DEFAULT_DATETIME,
            elapsed_term=sentinel.elapsed_term,
        )
        mock_calculate_emi.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            use_expected_term=True,
            principal_amount=sentinel.principal,
            interest_calculation_feature=sentinel.interest_rate_feature,
            principal_adjustments=[sentinel.principal_adjustments],
            balances=self.balances,
        )

    @patch.object(due_amount_calculation.emi, "update_emi")
    def test_scheduled_event_hook_requires_reamortisation_first_event(
        self,
        mock_update_emi: MagicMock,
        mock_calculate_due_principal: MagicMock,
        mock_transfer_principal_due: MagicMock,
        mock_update_due_amount_calculation_counter: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        counter_postings = [SentinelPosting("counter_posting")]
        mock_update_due_amount_calculation_counter.return_value = counter_postings
        mock_transfer_principal_due.return_value = []
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )
        mock_calculate_due_principal.return_value = sentinel.principal_due

        mock_should_trigger_reamortisation = MagicMock(return_value=True)
        mock_reamortisation_condition_feature = MagicMock(
            should_trigger_reamortisation=mock_should_trigger_reamortisation
        )
        mock_calculate_emi = MagicMock(return_value=sentinel.updated_emi)
        mock_term_details = MagicMock(return_value=(0, sentinel.remaining_term))
        mock_amortisation_feature = MagicMock(
            calculate_emi=mock_calculate_emi, term_details=mock_term_details
        )
        emi_postings = [SentinelPosting("emi_postings")]
        mock_update_emi.return_value = emi_postings
        mock_standard_instruction_details.return_value = sentinel_instruction_details

        account_creation_datetime = DEFAULT_DATETIME - relativedelta(months=1, days=10)
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                due_amount_calculation.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                    BalancesObservation(balances=self.balances, value_datetime=DEFAULT_DATETIME)
                )
            },
            last_execution_datetimes={due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: None},
            creation_date=account_creation_datetime,
        )

        expected_result = [
            CustomInstruction(
                postings=emi_postings + counter_postings,  # type: ignore
                override_all_restrictions=True,
                instruction_details=sentinel_instruction_details,
            )
        ]

        result = due_amount_calculation.schedule_logic(
            vault=mock_vault,
            hook_arguments=ScheduledEventHookArguments(
                effective_datetime=DEFAULT_DATETIME,
                event_type=sentinel.event_type,
            ),
            account_type=sentinel.account_type,
            reamortisation_condition_features=[mock_reamortisation_condition_feature],
            amortisation_feature=mock_amortisation_feature,
            interest_rate_feature=sentinel.interest_rate_feature,
            principal_adjustment_features=[sentinel.principal_adjustments],
        )

        self.assertListEqual(expected_result, result)
        mock_term_details.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            use_expected_term=True,
            interest_rate=sentinel.interest_rate_feature,
            balances=self.balances,
        )
        mock_update_emi.assert_called_once_with(
            account_id=ACCOUNT_ID,
            denomination=sentinel.denomination,
            current_emi=sentinel.emi,
            updated_emi=sentinel.updated_emi,
        )
        mock_should_trigger_reamortisation.assert_called_once_with(
            vault=mock_vault,
            period_start_datetime=account_creation_datetime,
            period_end_datetime=DEFAULT_DATETIME,
            elapsed_term=0,
        )
        mock_calculate_emi.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            use_expected_term=True,
            principal_amount=sentinel.principal,
            interest_calculation_feature=sentinel.interest_rate_feature,
            principal_adjustments=[sentinel.principal_adjustments],
            balances=self.balances,
        )

    @patch.object(due_amount_calculation.emi, "update_emi")
    def test_scheduled_event_hook_does_not_require_reamortisation(
        self,
        mock_update_emi: MagicMock,
        mock_calculate_due_principal: MagicMock,
        mock_transfer_principal_due: MagicMock,
        mock_update_due_amount_calculation_counter: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        counter_postings = [SentinelPosting("counter_posting")]
        mock_update_due_amount_calculation_counter.return_value = counter_postings
        transfer_postings = [SentinelPosting("xfer_posting")]
        mock_transfer_principal_due.return_value = transfer_postings
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )
        mock_calculate_due_principal.return_value = sentinel.principal_due
        mock_should_trigger_reamortisation = MagicMock(return_value=False)
        mock_reamortisation_condition_feature = MagicMock(
            should_trigger_reamortisation=mock_should_trigger_reamortisation
        )
        mock_calculate_emi = MagicMock(return_value=sentinel.updated_emi)
        mock_term_details = MagicMock(return_value=(sentinel.elapsed_term, sentinel.remaining_term))
        mock_amortisation_feature = MagicMock(
            calculate_emi=mock_calculate_emi, term_details=mock_term_details
        )
        mock_standard_instruction_details.return_value = sentinel_instruction_details

        last_execution_datetime = DEFAULT_DATETIME - relativedelta(months=1)
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                due_amount_calculation.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                    BalancesObservation(balances=self.balances, value_datetime=DEFAULT_DATETIME)
                )
            },
            last_execution_datetimes={
                due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: last_execution_datetime
            },
        )

        result = due_amount_calculation.schedule_logic(
            vault=mock_vault,
            hook_arguments=ScheduledEventHookArguments(
                effective_datetime=DEFAULT_DATETIME,
                event_type=sentinel.event_type,
            ),
            account_type=sentinel.account_type,
            reamortisation_condition_features=[mock_reamortisation_condition_feature],
            amortisation_feature=mock_amortisation_feature,
            interest_rate_feature=sentinel.interest_rate_feature,
        )

        self.assertListEqual(
            result,
            [
                CustomInstruction(
                    postings=transfer_postings + counter_postings,  # type: ignore
                    override_all_restrictions=True,
                    instruction_details=sentinel_instruction_details,
                )
            ],
        )

        mock_term_details.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            use_expected_term=True,
            interest_rate=sentinel.interest_rate_feature,
            balances=self.balances,
        )
        mock_update_emi.assert_not_called()
        mock_calculate_emi.assert_not_called()
        mock_should_trigger_reamortisation.assert_called_once_with(
            vault=mock_vault,
            period_start_datetime=last_execution_datetime,
            period_end_datetime=DEFAULT_DATETIME,
            elapsed_term=sentinel.elapsed_term,
        )

    @patch.object(due_amount_calculation.emi, "update_emi")
    def test_scheduled_event_hook_negative_override_final_event(
        self,
        mock_update_emi: MagicMock,
        mock_calculate_due_principal: MagicMock,
        mock_transfer_principal_due: MagicMock,
        mock_update_due_amount_calculation_counter: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        counter_postings = [SentinelPosting("counter_posting")]
        mock_update_due_amount_calculation_counter.return_value = counter_postings
        transfer_postings = [SentinelPosting("xfer_posting")]
        mock_transfer_principal_due.return_value = transfer_postings
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )
        mock_calculate_due_principal.return_value = sentinel.principal_due
        mock_should_trigger_reamortisation = MagicMock(return_value=False)
        mock_reamortisation_condition_feature = MagicMock(
            should_trigger_reamortisation=mock_should_trigger_reamortisation
        )
        mock_calculate_emi = MagicMock(return_value=sentinel.updated_emi)
        mock_term_details = MagicMock(return_value=(sentinel.elapsed_term, Decimal("1")))
        mock_amortisation_feature = MagicMock(
            calculate_emi=mock_calculate_emi,
            term_details=mock_term_details,
            override_final_event=False,
        )
        mock_standard_instruction_details.return_value = sentinel_instruction_details

        last_execution_datetime = DEFAULT_DATETIME - relativedelta(months=1)
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                due_amount_calculation.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                    BalancesObservation(balances=self.balances, value_datetime=DEFAULT_DATETIME)
                )
            },
            last_execution_datetimes={
                due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: last_execution_datetime
            },
        )

        result = due_amount_calculation.schedule_logic(
            vault=mock_vault,
            hook_arguments=ScheduledEventHookArguments(
                effective_datetime=DEFAULT_DATETIME,
                event_type=sentinel.event_type,
            ),
            account_type=sentinel.account_type,
            reamortisation_condition_features=[mock_reamortisation_condition_feature],
            amortisation_feature=mock_amortisation_feature,
            interest_rate_feature=sentinel.interest_rate_feature,
        )

        self.assertListEqual(
            result,
            [
                CustomInstruction(
                    postings=transfer_postings + counter_postings,  # type: ignore
                    override_all_restrictions=True,
                    instruction_details=sentinel_instruction_details,
                )
            ],
        )

        mock_term_details.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            use_expected_term=True,
            interest_rate=sentinel.interest_rate_feature,
            balances=self.balances,
        )
        mock_update_emi.assert_not_called()
        mock_calculate_emi.assert_not_called()
        mock_should_trigger_reamortisation.assert_called_once_with(
            vault=mock_vault,
            period_start_datetime=last_execution_datetime,
            period_end_datetime=DEFAULT_DATETIME,
            elapsed_term=sentinel.elapsed_term,
        )
        mock_calculate_due_principal.assert_called_once_with(
            remaining_principal=sentinel.principal,
            emi_interest_to_apply=Decimal("0"),
            emi=sentinel.emi,
            is_final_due_event=True,
        )

    @patch.object(due_amount_calculation.emi, "update_emi")
    def test_scheduled_event_hook_positive_override_final_event(
        self,
        mock_update_emi: MagicMock,
        mock_calculate_due_principal: MagicMock,
        mock_transfer_principal_due: MagicMock,
        mock_update_due_amount_calculation_counter: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        counter_postings = [SentinelPosting("counter_posting")]
        mock_update_due_amount_calculation_counter.return_value = counter_postings
        transfer_postings = [SentinelPosting("xfer_posting")]
        mock_transfer_principal_due.return_value = transfer_postings
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )
        mock_calculate_due_principal.return_value = sentinel.principal_due
        mock_should_trigger_reamortisation = MagicMock(return_value=False)
        mock_reamortisation_condition_feature = MagicMock(
            should_trigger_reamortisation=mock_should_trigger_reamortisation
        )
        mock_calculate_emi = MagicMock(return_value=sentinel.updated_emi)
        mock_term_details = MagicMock(return_value=(sentinel.elapsed_term, Decimal("1")))
        mock_amortisation_feature = MagicMock(
            calculate_emi=mock_calculate_emi,
            term_details=mock_term_details,
            override_final_event=True,
        )
        mock_standard_instruction_details.return_value = sentinel_instruction_details

        last_execution_datetime = DEFAULT_DATETIME - relativedelta(months=1)
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                due_amount_calculation.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                    BalancesObservation(balances=self.balances, value_datetime=DEFAULT_DATETIME)
                )
            },
            last_execution_datetimes={
                due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: last_execution_datetime
            },
        )

        result = due_amount_calculation.schedule_logic(
            vault=mock_vault,
            hook_arguments=ScheduledEventHookArguments(
                effective_datetime=DEFAULT_DATETIME,
                event_type=sentinel.event_type,
            ),
            account_type=sentinel.account_type,
            reamortisation_condition_features=[mock_reamortisation_condition_feature],
            amortisation_feature=mock_amortisation_feature,
            interest_rate_feature=sentinel.interest_rate_feature,
        )

        self.assertListEqual(
            result,
            [
                CustomInstruction(
                    postings=transfer_postings + counter_postings,  # type: ignore
                    override_all_restrictions=True,
                    instruction_details=sentinel_instruction_details,
                )
            ],
        )

        mock_term_details.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            use_expected_term=True,
            interest_rate=sentinel.interest_rate_feature,
            balances=self.balances,
        )
        mock_update_emi.assert_not_called()
        mock_calculate_emi.assert_not_called()
        mock_should_trigger_reamortisation.assert_called_once_with(
            vault=mock_vault,
            period_start_datetime=last_execution_datetime,
            period_end_datetime=DEFAULT_DATETIME,
            elapsed_term=sentinel.elapsed_term,
        )
        mock_calculate_due_principal.assert_called_once_with(
            remaining_principal=sentinel.principal,
            emi_interest_to_apply=Decimal("0"),
            emi=sentinel.emi,
            is_final_due_event=False,
        )


@patch.object(due_amount_calculation.utils, "standard_instruction_details")
@patch.object(due_amount_calculation.utils, "get_parameter")
@patch.object(due_amount_calculation, "get_principal", MagicMock(return_value=sentinel.principal))
@patch.object(due_amount_calculation, "get_emi", MagicMock(return_value=sentinel.emi))
@patch.object(due_amount_calculation, "update_due_amount_calculation_counter")
@patch.object(due_amount_calculation, "transfer_principal_due")
@patch.object(due_amount_calculation, "calculate_due_principal")
class SupervisorScheduleLogicTest(SupervisorDueAmountCalculationTest):
    def test_scheduled_event_hook_with_fetched_data_args_supervisor(
        self,
        mock_calculate_due_principal: MagicMock,
        mock_transfer_principal_due: MagicMock,
        mock_update_due_amount_calculation_counter: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_loan_vault = self.create_supervisee_mock()
        mock_main_vault = self.create_supervisee_mock()

        counter_postings = [SentinelPosting("counter_posting")]
        mock_update_due_amount_calculation_counter.return_value = counter_postings
        due_postings = [SentinelPosting("principal_due")]
        mock_transfer_principal_due.return_value = due_postings
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )
        mock_calculate_due_principal.return_value = sentinel.principal_due
        mock_standard_instruction_details.return_value = sentinel_instruction_details
        mock_amortisation_feature = MagicMock(term_details=MagicMock(return_value=(0, 2)))

        self.assertListEqual(
            due_amount_calculation.supervisor_schedule_logic(
                loan_vault=mock_loan_vault,
                main_vault=mock_main_vault,
                hook_arguments=SupervisorScheduledEventHookArguments(
                    effective_datetime=DEFAULT_DATETIME,
                    event_type=sentinel.event_type,
                    supervisee_pause_at_datetime={},
                ),
                amortisation_feature=mock_amortisation_feature,
                account_type=sentinel.account_type,
                balances=sentinel.balances,
                denomination=sentinel.denomination,
            ),
            [
                CustomInstruction(
                    postings=due_postings + counter_postings,  # type: ignore
                    override_all_restrictions=True,
                    instruction_details=sentinel_instruction_details,
                )
            ],
        )

        mock_calculate_due_principal.assert_called_once_with(
            remaining_principal=sentinel.principal,
            emi_interest_to_apply=Decimal(0),
            emi=sentinel.emi,
            is_final_due_event=False,
        )
        mock_transfer_principal_due.assert_called_once_with(
            customer_account=mock_loan_vault.account_id,
            principal_due=sentinel.principal_due,
            denomination=sentinel.denomination,
        )

    @patch.object(due_amount_calculation.utils, "get_balance_default_dict_from_mapping")
    def test_scheduled_event_hook_no_interest_application_feature_supervisor(
        self,
        mock_get_balance_default_dict_from_mapping: MagicMock,
        mock_calculate_due_principal: MagicMock,
        mock_transfer_principal_due: MagicMock,
        mock_update_due_amount_calculation_counter: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_get_balance_default_dict_from_mapping.return_value = self.balances
        mock_loan_vault = self.create_supervisee_mock(
            requires_fetched_balances=sentinel.fetched_balances,
        )
        mock_main_vault = self.create_supervisee_mock()

        counter_postings = [SentinelPosting("counter_posting")]
        mock_update_due_amount_calculation_counter.return_value = counter_postings
        due_postings = [SentinelPosting("principal_due")]
        mock_transfer_principal_due.return_value = due_postings
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )
        mock_calculate_due_principal.return_value = sentinel.principal_due
        mock_standard_instruction_details.return_value = sentinel_instruction_details
        mock_amortisation_feature = MagicMock(term_details=MagicMock(return_value=(0, 2)))

        self.assertListEqual(
            due_amount_calculation.supervisor_schedule_logic(
                loan_vault=mock_loan_vault,
                main_vault=mock_main_vault,
                hook_arguments=SupervisorScheduledEventHookArguments(
                    effective_datetime=DEFAULT_DATETIME,
                    event_type=sentinel.event_type,
                    supervisee_pause_at_datetime={},
                ),
                account_type=sentinel.account_type,
                amortisation_feature=mock_amortisation_feature,
            ),
            [
                CustomInstruction(
                    postings=due_postings + counter_postings,  # type: ignore
                    override_all_restrictions=True,
                    instruction_details=sentinel_instruction_details,
                )
            ],
        )

        mock_calculate_due_principal.assert_called_once_with(
            remaining_principal=sentinel.principal,
            emi_interest_to_apply=Decimal(0),
            emi=sentinel.emi,
            is_final_due_event=False,
        )
        mock_transfer_principal_due.assert_called_once_with(
            customer_account=mock_loan_vault.account_id,
            principal_due=sentinel.principal_due,
            denomination=sentinel.denomination,
        )

    @patch.object(due_amount_calculation.utils, "get_balance_default_dict_from_mapping")
    def test_scheduled_event_hook_no_due_principal_or_interest_supervisor(
        self,
        mock_get_balance_default_dict_from_mapping: MagicMock,
        mock_calculate_due_principal: MagicMock,
        mock_transfer_principal_due: MagicMock,
        mock_update_due_amount_calculation_counter: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_get_balance_default_dict_from_mapping.return_value = self.balances
        mock_loan_vault = self.create_supervisee_mock(
            requires_fetched_balances=sentinel.fetched_balances,
        )
        mock_main_vault = self.create_supervisee_mock()

        mock_update_due_amount_calculation_counter.return_value = []
        mock_transfer_principal_due.return_value = []
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )
        mock_calculate_due_principal.return_value = sentinel.principal_due
        mock_standard_instruction_details.return_value = sentinel_instruction_details
        mock_amortisation_feature = MagicMock(term_details=MagicMock(return_value=(0, 2)))

        self.assertListEqual(
            due_amount_calculation.supervisor_schedule_logic(
                loan_vault=mock_loan_vault,
                main_vault=mock_main_vault,
                hook_arguments=SupervisorScheduledEventHookArguments(
                    effective_datetime=DEFAULT_DATETIME,
                    event_type=sentinel.event_type,
                    supervisee_pause_at_datetime={},
                ),
                account_type=sentinel.account_type,
                amortisation_feature=mock_amortisation_feature,
            ),
            [],
        )

        mock_calculate_due_principal.assert_called_once_with(
            remaining_principal=sentinel.principal,
            emi_interest_to_apply=Decimal(0),
            emi=sentinel.emi,
            is_final_due_event=False,
        )
        mock_transfer_principal_due.assert_called_once_with(
            customer_account=mock_loan_vault.account_id,
            principal_due=sentinel.principal_due,
            denomination=sentinel.denomination,
        )

    @patch.object(due_amount_calculation.utils, "get_balance_default_dict_from_mapping")
    def test_scheduled_event_hook_with_interest_and_principal_due_supervisor(
        self,
        mock_get_balance_default_dict_from_mapping: MagicMock,
        mock_calculate_due_principal: MagicMock,
        mock_transfer_principal_due: MagicMock,
        mock_update_due_amount_calculation_counter: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        principal_due_postings = [SentinelPosting("principal_due")]
        interest_due_postings = [SentinelPosting("interest_due")]
        counter_postings = [SentinelPosting("counter_posting")]

        mock_interest_amounts = lending_interfaces.InterestAmounts(
            emi_accrued=sentinel.emi_accrued,
            emi_rounded_accrued=sentinel.emi_rounded_accrued,
            non_emi_accrued=sentinel.non_emi_accrued,
            non_emi_rounded_accrued=Decimal("0.12"),
            total_rounded=Decimal("1.23"),
        )
        mock_interest_application_feature = MagicMock(
            get_interest_to_apply=MagicMock(return_value=mock_interest_amounts),
            apply_interest=MagicMock(return_value=interest_due_postings),
        )
        mock_get_balance_default_dict_from_mapping.return_value = self.balances
        mock_loan_vault = self.create_supervisee_mock(
            requires_fetched_balances=sentinel.fetched_balances,
        )
        mock_main_vault = self.create_supervisee_mock()

        mock_transfer_principal_due.return_value = principal_due_postings
        mock_update_due_amount_calculation_counter.return_value = counter_postings
        mock_amortisation_feature = MagicMock(term_details=MagicMock(return_value=(0, 2)))
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )
        mock_calculate_due_principal.return_value = sentinel.principal_due
        mock_standard_instruction_details.return_value = sentinel_instruction_details

        expected_postings = interest_due_postings + principal_due_postings + counter_postings
        self.assertListEqual(
            due_amount_calculation.supervisor_schedule_logic(
                loan_vault=mock_loan_vault,
                main_vault=mock_main_vault,
                hook_arguments=SupervisorScheduledEventHookArguments(
                    effective_datetime=DEFAULT_DATETIME,
                    event_type=sentinel.event_type,
                    supervisee_pause_at_datetime={},
                ),
                account_type=sentinel.account_type,
                amortisation_feature=mock_amortisation_feature,
                interest_application_feature=mock_interest_application_feature,
            ),
            [
                CustomInstruction(
                    postings=expected_postings,  # type: ignore
                    override_all_restrictions=True,
                    instruction_details=sentinel_instruction_details,
                )
            ],
        )

        mock_calculate_due_principal.assert_called_once_with(
            remaining_principal=sentinel.principal,
            emi_interest_to_apply=Decimal("1.11"),
            emi=sentinel.emi,
            is_final_due_event=False,
        )
        mock_transfer_principal_due.assert_called_once_with(
            customer_account=mock_loan_vault.account_id,
            principal_due=sentinel.principal_due,
            denomination=sentinel.denomination,
        )

    @patch.object(due_amount_calculation.emi, "update_emi")
    @patch.object(due_amount_calculation.utils, "get_balance_default_dict_from_mapping")
    def test_scheduled_event_hook_requires_reamortisation_supervisor(
        self,
        mock_get_balance_default_dict_from_mapping: MagicMock,
        mock_update_emi: MagicMock,
        mock_calculate_due_principal: MagicMock,
        mock_transfer_principal_due: MagicMock,
        mock_update_due_amount_calculation_counter: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        counter_postings = [SentinelPosting("counter_posting")]
        mock_update_due_amount_calculation_counter.return_value = counter_postings
        mock_transfer_principal_due.return_value = []
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )
        mock_calculate_due_principal.return_value = sentinel.principal_due

        mock_should_trigger_reamortisation = MagicMock(return_value=True)
        mock_reamortisation_condition_feature = MagicMock(
            should_trigger_reamortisation=mock_should_trigger_reamortisation
        )
        mock_calculate_emi = MagicMock(return_value=sentinel.updated_emi)
        mock_term_details = MagicMock(return_value=(sentinel.elapsed_term, sentinel.remaining_term))
        mock_amortisation_feature = MagicMock(
            calculate_emi=mock_calculate_emi, term_details=mock_term_details
        )
        emi_postings = [SentinelPosting("emi_postings")]
        mock_update_emi.return_value = emi_postings
        mock_standard_instruction_details.return_value = sentinel_instruction_details

        last_execution_datetime = DEFAULT_DATETIME - relativedelta(months=1)
        mock_get_balance_default_dict_from_mapping.return_value = self.balances
        mock_loan_vault = self.create_supervisee_mock(
            requires_fetched_balances=sentinel.fetched_balances,
        )
        mock_main_vault = self.create_supervisee_mock(
            last_execution_datetimes={
                due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: last_execution_datetime
            },
        )

        expected_result = [
            CustomInstruction(
                postings=emi_postings + counter_postings,  # type: ignore
                override_all_restrictions=True,
                instruction_details=sentinel_instruction_details,
            )
        ]

        result = due_amount_calculation.supervisor_schedule_logic(
            loan_vault=mock_loan_vault,
            main_vault=mock_main_vault,
            hook_arguments=SupervisorScheduledEventHookArguments(
                effective_datetime=DEFAULT_DATETIME,
                event_type=sentinel.event_type,
                supervisee_pause_at_datetime={},
            ),
            account_type=sentinel.account_type,
            reamortisation_condition_features=[mock_reamortisation_condition_feature],
            amortisation_feature=mock_amortisation_feature,
            interest_rate_feature=sentinel.interest_rate_feature,
            principal_adjustment_features=[sentinel.principal_adjustments],
        )

        self.assertListEqual(expected_result, result)
        mock_term_details.assert_called_once_with(
            loan_vault=mock_loan_vault,
            main_vault=mock_main_vault,
            effective_datetime=DEFAULT_DATETIME,
            use_expected_term=True,
            interest_rate=sentinel.interest_rate_feature,
            balances=self.balances,
        )
        mock_update_emi.assert_called_once_with(
            account_id=ACCOUNT_ID,
            denomination=sentinel.denomination,
            current_emi=sentinel.emi,
            updated_emi=sentinel.updated_emi,
        )
        mock_should_trigger_reamortisation.assert_called_once_with(
            loan_vault=mock_loan_vault,
            main_vault=mock_main_vault,
            period_start_datetime=last_execution_datetime,
            period_end_datetime=DEFAULT_DATETIME,
            elapsed_term=sentinel.elapsed_term,
        )
        mock_calculate_emi.assert_called_once_with(
            loan_vault=mock_loan_vault,
            main_vault=mock_main_vault,
            effective_datetime=DEFAULT_DATETIME,
            use_expected_term=True,
            principal_amount=sentinel.principal,
            interest_calculation_feature=sentinel.interest_rate_feature,
            principal_adjustments=[sentinel.principal_adjustments],
            balances=self.balances,
        )

    @patch.object(due_amount_calculation.emi, "update_emi")
    @patch.object(due_amount_calculation.utils, "get_balance_default_dict_from_mapping")
    def test_scheduled_event_hook_requires_reamortisation_first_event_supervisor(
        self,
        mock_get_balance_default_dict_from_mapping: MagicMock,
        mock_update_emi: MagicMock,
        mock_calculate_due_principal: MagicMock,
        mock_transfer_principal_due: MagicMock,
        mock_update_due_amount_calculation_counter: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        counter_postings = [SentinelPosting("counter_posting")]
        mock_update_due_amount_calculation_counter.return_value = counter_postings
        mock_transfer_principal_due.return_value = []
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )
        mock_calculate_due_principal.return_value = sentinel.principal_due

        mock_should_trigger_reamortisation = MagicMock(return_value=True)
        mock_reamortisation_condition_feature = MagicMock(
            should_trigger_reamortisation=mock_should_trigger_reamortisation
        )
        mock_calculate_emi = MagicMock(return_value=sentinel.updated_emi)
        mock_term_details = MagicMock(return_value=(0, sentinel.remaining_term))
        mock_amortisation_feature = MagicMock(
            calculate_emi=mock_calculate_emi, term_details=mock_term_details
        )
        emi_postings = [SentinelPosting("emi_postings")]
        mock_update_emi.return_value = emi_postings
        mock_standard_instruction_details.return_value = sentinel_instruction_details

        account_creation_datetime = DEFAULT_DATETIME - relativedelta(months=1, days=10)
        last_execution_datetime = DEFAULT_DATETIME - relativedelta(months=1)
        mock_get_balance_default_dict_from_mapping.return_value = self.balances
        mock_loan_vault = self.create_supervisee_mock(
            requires_fetched_balances=sentinel.fetched_balances,
            creation_date=account_creation_datetime,
        )
        mock_main_vault = self.create_supervisee_mock(
            last_execution_datetimes={
                due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: last_execution_datetime
            },
        )

        expected_result = [
            CustomInstruction(
                postings=emi_postings + counter_postings,  # type: ignore
                override_all_restrictions=True,
                instruction_details=sentinel_instruction_details,
            )
        ]

        result = due_amount_calculation.supervisor_schedule_logic(
            loan_vault=mock_loan_vault,
            main_vault=mock_main_vault,
            hook_arguments=SupervisorScheduledEventHookArguments(
                effective_datetime=DEFAULT_DATETIME,
                event_type=sentinel.event_type,
                supervisee_pause_at_datetime={},
            ),
            account_type=sentinel.account_type,
            reamortisation_condition_features=[mock_reamortisation_condition_feature],
            amortisation_feature=mock_amortisation_feature,
            interest_rate_feature=sentinel.interest_rate_feature,
            principal_adjustment_features=[sentinel.principal_adjustments],
        )

        self.assertListEqual(expected_result, result)
        mock_term_details.assert_called_once_with(
            loan_vault=mock_loan_vault,
            main_vault=mock_main_vault,
            effective_datetime=DEFAULT_DATETIME,
            use_expected_term=True,
            interest_rate=sentinel.interest_rate_feature,
            balances=self.balances,
        )
        mock_update_emi.assert_called_once_with(
            account_id=ACCOUNT_ID,
            denomination=sentinel.denomination,
            current_emi=sentinel.emi,
            updated_emi=sentinel.updated_emi,
        )
        mock_should_trigger_reamortisation.assert_called_once_with(
            loan_vault=mock_loan_vault,
            main_vault=mock_main_vault,
            period_start_datetime=account_creation_datetime,
            period_end_datetime=DEFAULT_DATETIME,
            elapsed_term=0,
        )
        mock_calculate_emi.assert_called_once_with(
            loan_vault=mock_loan_vault,
            main_vault=mock_main_vault,
            effective_datetime=DEFAULT_DATETIME,
            use_expected_term=True,
            principal_amount=sentinel.principal,
            interest_calculation_feature=sentinel.interest_rate_feature,
            principal_adjustments=[sentinel.principal_adjustments],
            balances=self.balances,
        )

    @patch.object(due_amount_calculation.emi, "update_emi")
    @patch.object(due_amount_calculation.utils, "get_balance_default_dict_from_mapping")
    def test_scheduled_event_hook_does_not_require_reamortisation_supervisor(
        self,
        mock_get_balance_default_dict_from_mapping: MagicMock,
        mock_update_emi: MagicMock,
        mock_calculate_due_principal: MagicMock,
        mock_transfer_principal_due: MagicMock,
        mock_update_due_amount_calculation_counter: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        counter_postings = [SentinelPosting("counter_posting")]
        mock_update_due_amount_calculation_counter.return_value = counter_postings
        transfer_postings = [SentinelPosting("xfer_posting")]
        mock_transfer_principal_due.return_value = transfer_postings
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )
        mock_calculate_due_principal.return_value = sentinel.principal_due
        mock_should_trigger_reamortisation = MagicMock(return_value=False)
        mock_reamortisation_condition_feature = MagicMock(
            should_trigger_reamortisation=mock_should_trigger_reamortisation
        )
        mock_calculate_emi = MagicMock(return_value=sentinel.updated_emi)
        mock_term_details = MagicMock(return_value=(sentinel.elapsed_term, sentinel.remaining_term))
        mock_amortisation_feature = MagicMock(
            calculate_emi=mock_calculate_emi, term_details=mock_term_details
        )
        mock_standard_instruction_details.return_value = sentinel_instruction_details

        last_execution_datetime = DEFAULT_DATETIME - relativedelta(months=1)
        mock_get_balance_default_dict_from_mapping.return_value = self.balances
        mock_loan_vault = self.create_supervisee_mock(
            requires_fetched_balances=sentinel.fetched_balances,
        )
        mock_main_vault = self.create_supervisee_mock(
            last_execution_datetimes={
                due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: last_execution_datetime
            },
        )

        result = due_amount_calculation.supervisor_schedule_logic(
            loan_vault=mock_loan_vault,
            main_vault=mock_main_vault,
            hook_arguments=SupervisorScheduledEventHookArguments(
                effective_datetime=DEFAULT_DATETIME,
                event_type=sentinel.event_type,
                supervisee_pause_at_datetime={},
            ),
            account_type=sentinel.account_type,
            reamortisation_condition_features=[mock_reamortisation_condition_feature],
            amortisation_feature=mock_amortisation_feature,
            interest_rate_feature=sentinel.interest_rate_feature,
        )

        self.assertListEqual(
            result,
            [
                CustomInstruction(
                    postings=transfer_postings + counter_postings,  # type: ignore
                    override_all_restrictions=True,
                    instruction_details=sentinel_instruction_details,
                )
            ],
        )

        mock_term_details.assert_called_once_with(
            loan_vault=mock_loan_vault,
            main_vault=mock_main_vault,
            effective_datetime=DEFAULT_DATETIME,
            use_expected_term=True,
            interest_rate=sentinel.interest_rate_feature,
            balances=self.balances,
        )
        mock_update_emi.assert_not_called()
        mock_calculate_emi.assert_not_called()
        mock_should_trigger_reamortisation.assert_called_once_with(
            loan_vault=mock_loan_vault,
            main_vault=mock_main_vault,
            period_start_datetime=last_execution_datetime,
            period_end_datetime=DEFAULT_DATETIME,
            elapsed_term=sentinel.elapsed_term,
        )
        mock_get_balance_default_dict_from_mapping.assert_called_once_with(
            mapping=sentinel.fetched_balances,
            effective_datetime=DEFAULT_DATETIME,
        )

    @patch.object(due_amount_calculation.emi, "update_emi")
    @patch.object(due_amount_calculation.utils, "get_balance_default_dict_from_mapping")
    def test_scheduled_event_hook_negative_override_final_event_supervisor(
        self,
        mock_get_balance_default_dict_from_mapping: MagicMock,
        mock_update_emi: MagicMock,
        mock_calculate_due_principal: MagicMock,
        mock_transfer_principal_due: MagicMock,
        mock_update_due_amount_calculation_counter: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        counter_postings = [SentinelPosting("counter_posting")]
        mock_update_due_amount_calculation_counter.return_value = counter_postings
        transfer_postings = [SentinelPosting("xfer_posting")]
        mock_transfer_principal_due.return_value = transfer_postings
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )
        mock_calculate_due_principal.return_value = sentinel.principal_due
        mock_should_trigger_reamortisation = MagicMock(return_value=False)
        mock_reamortisation_condition_feature = MagicMock(
            should_trigger_reamortisation=mock_should_trigger_reamortisation
        )
        mock_calculate_emi = MagicMock(return_value=sentinel.updated_emi)
        mock_term_details = MagicMock(return_value=(sentinel.elapsed_term, Decimal("1")))
        mock_amortisation_feature = MagicMock(
            calculate_emi=mock_calculate_emi,
            term_details=mock_term_details,
            override_final_event=False,
        )
        mock_standard_instruction_details.return_value = sentinel_instruction_details

        last_execution_datetime = DEFAULT_DATETIME - relativedelta(months=1)
        mock_get_balance_default_dict_from_mapping.return_value = self.balances
        mock_loan_vault = self.create_supervisee_mock(
            requires_fetched_balances=sentinel.fetched_balances,
        )
        mock_main_vault = self.create_supervisee_mock(
            last_execution_datetimes={
                due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: last_execution_datetime
            },
        )

        result = due_amount_calculation.supervisor_schedule_logic(
            loan_vault=mock_loan_vault,
            main_vault=mock_main_vault,
            hook_arguments=SupervisorScheduledEventHookArguments(
                effective_datetime=DEFAULT_DATETIME,
                event_type=sentinel.event_type,
                supervisee_pause_at_datetime={},
            ),
            account_type=sentinel.account_type,
            reamortisation_condition_features=[mock_reamortisation_condition_feature],
            amortisation_feature=mock_amortisation_feature,
            interest_rate_feature=sentinel.interest_rate_feature,
        )

        self.assertListEqual(
            result,
            [
                CustomInstruction(
                    postings=transfer_postings + counter_postings,  # type: ignore
                    override_all_restrictions=True,
                    instruction_details=sentinel_instruction_details,
                )
            ],
        )

        mock_term_details.assert_called_once_with(
            loan_vault=mock_loan_vault,
            main_vault=mock_main_vault,
            effective_datetime=DEFAULT_DATETIME,
            use_expected_term=True,
            interest_rate=sentinel.interest_rate_feature,
            balances=self.balances,
        )
        mock_update_emi.assert_not_called()
        mock_calculate_emi.assert_not_called()
        mock_should_trigger_reamortisation.assert_called_once_with(
            loan_vault=mock_loan_vault,
            main_vault=mock_main_vault,
            period_start_datetime=last_execution_datetime,
            period_end_datetime=DEFAULT_DATETIME,
            elapsed_term=sentinel.elapsed_term,
        )
        mock_calculate_due_principal.assert_called_once_with(
            remaining_principal=sentinel.principal,
            emi_interest_to_apply=Decimal("0"),
            emi=sentinel.emi,
            is_final_due_event=True,
        )

    @patch.object(due_amount_calculation.emi, "update_emi")
    @patch.object(due_amount_calculation.utils, "get_balance_default_dict_from_mapping")
    def test_scheduled_event_hook_positive_override_final_event_supervisor(
        self,
        mock_get_balance_default_dict_from_mapping: MagicMock,
        mock_update_emi: MagicMock,
        mock_calculate_due_principal: MagicMock,
        mock_transfer_principal_due: MagicMock,
        mock_update_due_amount_calculation_counter: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        counter_postings = [SentinelPosting("counter_posting")]
        mock_update_due_amount_calculation_counter.return_value = counter_postings
        transfer_postings = [SentinelPosting("xfer_posting")]
        mock_transfer_principal_due.return_value = transfer_postings
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )
        mock_calculate_due_principal.return_value = sentinel.principal_due
        mock_should_trigger_reamortisation = MagicMock(return_value=False)
        mock_reamortisation_condition_feature = MagicMock(
            should_trigger_reamortisation=mock_should_trigger_reamortisation
        )
        mock_calculate_emi = MagicMock(return_value=sentinel.updated_emi)
        mock_term_details = MagicMock(return_value=(sentinel.elapsed_term, Decimal("1")))
        mock_amortisation_feature = MagicMock(
            calculate_emi=mock_calculate_emi,
            term_details=mock_term_details,
            override_final_event=True,
        )
        mock_standard_instruction_details.return_value = sentinel_instruction_details

        last_execution_datetime = DEFAULT_DATETIME - relativedelta(months=1)
        mock_get_balance_default_dict_from_mapping.return_value = self.balances
        mock_loan_vault = self.create_supervisee_mock(
            requires_fetched_balances=sentinel.fetched_balances,
        )
        mock_main_vault = self.create_supervisee_mock(
            last_execution_datetimes={
                due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: last_execution_datetime
            },
        )

        result = due_amount_calculation.supervisor_schedule_logic(
            loan_vault=mock_loan_vault,
            main_vault=mock_main_vault,
            hook_arguments=SupervisorScheduledEventHookArguments(
                effective_datetime=DEFAULT_DATETIME,
                event_type=sentinel.event_type,
                supervisee_pause_at_datetime={},
            ),
            account_type=sentinel.account_type,
            reamortisation_condition_features=[mock_reamortisation_condition_feature],
            amortisation_feature=mock_amortisation_feature,
            interest_rate_feature=sentinel.interest_rate_feature,
        )

        self.assertListEqual(
            result,
            [
                CustomInstruction(
                    postings=transfer_postings + counter_postings,  # type: ignore
                    override_all_restrictions=True,
                    instruction_details=sentinel_instruction_details,
                )
            ],
        )

        mock_term_details.assert_called_once_with(
            loan_vault=mock_loan_vault,
            main_vault=mock_main_vault,
            effective_datetime=DEFAULT_DATETIME,
            use_expected_term=True,
            interest_rate=sentinel.interest_rate_feature,
            balances=self.balances,
        )
        mock_update_emi.assert_not_called()
        mock_calculate_emi.assert_not_called()
        mock_should_trigger_reamortisation.assert_called_once_with(
            loan_vault=mock_loan_vault,
            main_vault=mock_main_vault,
            period_start_datetime=last_execution_datetime,
            period_end_datetime=DEFAULT_DATETIME,
            elapsed_term=sentinel.elapsed_term,
        )
        mock_calculate_due_principal.assert_called_once_with(
            remaining_principal=sentinel.principal,
            emi_interest_to_apply=Decimal("0"),
            emi=sentinel.emi,
            is_final_due_event=False,
        )


class DueAmountCalculationScheduleTest(DueAmountCalculationTest):
    def test_due_amount_calculation_event_types(self):
        event_types = due_amount_calculation.event_types(product_name="product_a")
        self.assertListEqual(
            event_types,
            [
                SmartContractEventType(
                    name=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                    scheduler_tag_ids=[
                        f"PRODUCT_A_{due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT}_AST"
                    ],
                )
            ],
        )

    def test_due_amount_calculation_supervisor_event_types(self):
        event_types = due_amount_calculation.supervisor_event_types(product_name="product_a")
        self.assertListEqual(
            event_types,
            [
                SupervisorContractEventType(
                    name=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                    scheduler_tag_ids=[
                        f"PRODUCT_A_{due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT}_AST"
                    ],
                )
            ],
        )

    @patch.object(due_amount_calculation.utils, "monthly_scheduled_event")
    def test_due_amount_scheduled_event_starts_a_month_after_opening(
        self, mock_monthly_scheduled_event: MagicMock
    ):
        mock_vault = MagicMock()
        mock_monthly_scheduled_event.return_value = sentinel.monthly_scheduled_event

        scheduled_events = due_amount_calculation.scheduled_events(
            vault=mock_vault,
            account_opening_datetime=datetime(2020, 1, 2, 3, 4, 5, tzinfo=ZoneInfo("UTC")),
        )

        self.assertDictEqual(
            scheduled_events,
            {due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: sentinel.monthly_scheduled_event},
        )
        mock_monthly_scheduled_event.assert_called_once_with(
            vault=mock_vault,
            start_datetime=datetime(2020, 2, 2, tzinfo=ZoneInfo("UTC")),
            parameter_prefix="due_amount_calculation",
        )


@patch.object(due_amount_calculation.utils, "get_schedule_time_from_parameters")
@patch.object(due_amount_calculation.utils, "get_parameter")
class FirstDueAmountCalculationDate(DueAmountCalculationTest):
    def test_first_due_amount_calculation_date_opening_before_due_amount_calculation_day(
        self, mock_get_parameter: MagicMock, mock_get_schedule_time_from_parameters: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: 4}
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0
        mock_vault = MagicMock(
            get_account_creation_datetime=MagicMock(
                return_value=datetime(2020, 1, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
            )
        )

        self.assertEqual(
            due_amount_calculation.get_first_due_amount_calculation_datetime(vault=mock_vault),
            datetime(2020, 2, 4, 0, 1, 0, tzinfo=ZoneInfo("UTC")),
        )

    def test_first_due_amount_calculation_date_opening_after_due_amount_calculation_day(
        self, mock_get_parameter: MagicMock, mock_get_schedule_time_from_parameters: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: 4}
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0
        mock_vault = MagicMock(
            get_account_creation_datetime=MagicMock(
                return_value=datetime(2020, 1, 5, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
            )
        )

        self.assertEqual(
            due_amount_calculation.get_first_due_amount_calculation_datetime(vault=mock_vault),
            datetime(2020, 3, 4, 0, 1, 0, tzinfo=ZoneInfo("UTC")),
        )

    def test_first_due_amount_calculation_date_opening_on_due_amount_calculation_day(
        self, mock_get_parameter: MagicMock, mock_get_schedule_time_from_parameters: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: 4}
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0
        mock_vault = MagicMock(
            get_account_creation_datetime=MagicMock(
                return_value=datetime(2020, 1, 4, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
            )
        )

        self.assertEqual(
            due_amount_calculation.get_first_due_amount_calculation_datetime(vault=mock_vault),
            datetime(2020, 2, 4, 0, 1, 0, tzinfo=ZoneInfo("UTC")),
        )


@patch.object(due_amount_calculation.utils, "reset_tracker_balances")
class GetResidualCleanupPostingsTest(DueAmountCalculationTest):
    def test_get_residual_cleanup_postings_with_postings(
        self, mock_reset_tracker_balances: MagicMock
    ):
        mock_reset_tracker_balances.return_value = [sentinel.postings]

        result = due_amount_calculation.get_residual_cleanup_postings(
            balances=sentinel.balances,
            account_id=sentinel.account_id,
            denomination=sentinel.denomination,
        )

        self.assertListEqual(result, [sentinel.postings])

        mock_reset_tracker_balances.assert_called_once_with(
            balances=sentinel.balances,
            account_id=sentinel.account_id,
            tracker_addresses=[
                "DUE_CALCULATION_EVENT_COUNTER",
            ],
            contra_address="INTERNAL_CONTRA",
            denomination=sentinel.denomination,
            tside=Tside.ASSET,
        )

    def test_get_residual_cleanup_postings_no_postings(
        self, mock_reset_tracker_balances: MagicMock
    ):
        mock_reset_tracker_balances.return_value = []

        result = due_amount_calculation.get_residual_cleanup_postings(
            balances=sentinel.balances,
            account_id=sentinel.account_id,
            denomination=sentinel.denomination,
        )

        self.assertListEqual(result, [])

        mock_reset_tracker_balances.assert_called_once_with(
            balances=sentinel.balances,
            account_id=sentinel.account_id,
            tracker_addresses=[
                "DUE_CALCULATION_EVENT_COUNTER",
            ],
            contra_address="INTERNAL_CONTRA",
            denomination=sentinel.denomination,
            tside=Tside.ASSET,
        )


@patch.object(due_amount_calculation.utils, "create_postings")
class UpdateTrackerTest(DueAmountCalculationTest):
    def test_update_due_amount_calculation_counter(self, mock_create_postings: MagicMock):
        mock_create_postings.return_value = [sentinel.postings]
        result = due_amount_calculation.update_due_amount_calculation_counter(
            account_id=sentinel.account_id, denomination=sentinel.denomination
        )
        self.assertListEqual(result, [sentinel.postings])

        mock_create_postings.assert_called_once_with(
            amount=Decimal("1"),
            debit_account=sentinel.account_id,
            debit_address="DUE_CALCULATION_EVENT_COUNTER",
            credit_account=sentinel.account_id,
            credit_address="INTERNAL_CONTRA",
            denomination=sentinel.denomination,
        )


@patch.object(due_amount_calculation.utils, "get_schedule_time_from_parameters")
@patch.object(due_amount_calculation.utils, "get_parameter")
class NextDueAmountCalculationDate(DueAmountCalculationTest):
    def test_next_due_amount_calculation_dt_opening_before_due_amount_calculation_day(
        self, mock_get_parameter: MagicMock, mock_get_schedule_time_from_parameters: MagicMock
    ):
        """
        If effective_dt is in the opening period
        First due amount calculation date occurs skips a month from account opening
        if chosen day is not greater than the account opening day.

        This is to ensure the first due amount calc date is always at least 1 month
        from opening date, on the chosen due amount calculation day.
        """
        start_dt = datetime(2020, 1, 2, 3, 4, 5, tzinfo=ZoneInfo("UTC"))

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: 1}
        )
        mock_get_schedule_time_from_parameters.return_value = 2, 3, 4
        mock_vault = MagicMock(
            get_account_creation_datetime=MagicMock(return_value=start_dt),
            get_last_execution_datetime=MagicMock(return_value=None),
        )

        expected_next_repayment_dt = datetime(2020, 3, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))

        next_due_amount_calc_dt = due_amount_calculation.get_next_due_amount_calculation_datetime(
            vault=mock_vault,
            effective_datetime=start_dt,
            elapsed_term=0,
            remaining_term=sentinel.remaining_term,
        )

        self.assertEqual(expected_next_repayment_dt, next_due_amount_calc_dt)
        mock_get_parameter.assert_called_once_with(
            vault=mock_vault, name="due_amount_calculation_day"
        )

    def test_next_due_amount_calculation_dt_with_due_amount_calculation_day_supplied(
        self, mock_get_parameter: MagicMock, mock_get_schedule_time_from_parameters: MagicMock
    ):
        """
        Use the due_amount_calculation_day arg rather than defaulting to None
        """
        start_dt = datetime(2020, 1, 2, 3, 4, 5, tzinfo=ZoneInfo("UTC"))

        mock_get_schedule_time_from_parameters.return_value = 2, 3, 4
        last_execution_dt = datetime(2020, 2, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        mock_vault = MagicMock(
            get_account_creation_datetime=MagicMock(return_value=start_dt),
            get_last_execution_datetime=MagicMock(return_value=last_execution_dt),
        )

        expected_next_repayment_dt = datetime(2020, 3, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))

        next_due_amount_calc_dt = due_amount_calculation.get_next_due_amount_calculation_datetime(
            vault=mock_vault,
            effective_datetime=start_dt,
            elapsed_term=1,
            remaining_term=12,
            due_amount_calculation_day=1,
        )

        self.assertEqual(expected_next_repayment_dt, next_due_amount_calc_dt)
        mock_get_parameter.assert_not_called()

    def test_next_due_amount_calculation_dt_opening_after_due_amount_calculation_day(
        self, mock_get_parameter: MagicMock, mock_get_schedule_time_from_parameters: MagicMock
    ):
        """
        If effective_dt is in the opening period
        First due amount calculation date occurs in the following month from account opening
        if chosen day is greater the account opening day
        """
        start_dt = datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: 1}
        )
        mock_get_schedule_time_from_parameters.return_value = 2, 3, 4
        mock_vault = MagicMock(
            get_account_creation_datetime=MagicMock(return_value=start_dt),
            get_last_execution_datetime=MagicMock(return_value=None),
        )

        expected_next_repayment_dt = datetime(2020, 2, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        next_due_amount_calc_dt = due_amount_calculation.get_next_due_amount_calculation_datetime(
            vault=mock_vault,
            effective_datetime=start_dt,
            elapsed_term=0,
            remaining_term=sentinel.remaining_term,
        )

        self.assertEqual(expected_next_repayment_dt, next_due_amount_calc_dt)

    def test_next_due_amount_calculation_dt_opening_on_due_amount_calculation_day(
        self, mock_get_parameter: MagicMock, mock_get_schedule_time_from_parameters: MagicMock
    ):
        """
        If effective_dt is in the opening period
        First due amount calculation date can be exactly one month after account opening
        """
        start_dt = datetime(2020, 1, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: 1}
        )
        mock_get_schedule_time_from_parameters.return_value = 2, 3, 4
        mock_vault = MagicMock(
            get_account_creation_datetime=MagicMock(return_value=start_dt),
            get_last_execution_datetime=MagicMock(return_value=None),
        )
        expected_next_repayment_dt = datetime(2020, 2, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        next_due_amount_calc_dt = due_amount_calculation.get_next_due_amount_calculation_datetime(
            vault=mock_vault,
            effective_datetime=start_dt,
            elapsed_term=0,
            remaining_term=sentinel.remaining_term,
        )

        self.assertEqual(expected_next_repayment_dt, next_due_amount_calc_dt)

    def test_next_due_amount_calculation_dt_mid_cycle_a_day_before_due_amount_calculation_day(
        self, mock_get_parameter: MagicMock, mock_get_schedule_time_from_parameters: MagicMock
    ):
        """
        IF effective_dt is not in the opening period
        AND
        IF effective dt is a day before the expected calculation day,
        then next due amount calculation day is expected to still be 1 month after last execution dt
        """
        start_dt = datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: 1}
        )
        mock_get_schedule_time_from_parameters.return_value = 2, 3, 4
        last_execution_dt = datetime(2020, 2, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        mock_vault = MagicMock(
            get_account_creation_datetime=MagicMock(return_value=start_dt),
            get_last_execution_datetime=MagicMock(return_value=last_execution_dt),
        )
        effective_dt = datetime(2020, 2, 29, tzinfo=ZoneInfo("UTC"))

        expected_next_repayment_dt = datetime(2020, 3, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        next_due_amount_calc_dt = due_amount_calculation.get_next_due_amount_calculation_datetime(
            vault=mock_vault,
            effective_datetime=effective_dt,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=sentinel.remaining_term,
        )

        self.assertEqual(expected_next_repayment_dt, next_due_amount_calc_dt)

    def test_next_due_amount_calculation_dt_mid_cycle_on_due_amount_calculation_day_before_runtime(
        self, mock_get_parameter: MagicMock, mock_get_schedule_time_from_parameters: MagicMock
    ):
        """
        IF effective_dt is not in the opening period
        AND
        IF effective dt is on the same day but an hour before the expected calculation day,
        then next due amount calculation day is expected to still be 1 month after last execution dt
        """
        start_dt = datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: 1}
        )
        mock_get_schedule_time_from_parameters.return_value = 2, 3, 4
        last_execution_dt = datetime(2020, 2, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        mock_vault = MagicMock(
            get_account_creation_datetime=MagicMock(return_value=start_dt),
            get_last_execution_datetime=MagicMock(return_value=last_execution_dt),
        )
        effective_dt = datetime(2020, 3, 1, 2, 3, 3, tzinfo=ZoneInfo("UTC"))

        expected_next_repayment_dt = datetime(2020, 3, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        next_due_amount_calc_dt = due_amount_calculation.get_next_due_amount_calculation_datetime(
            vault=mock_vault,
            effective_datetime=effective_dt,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=sentinel.remaining_term,
        )

        self.assertEqual(expected_next_repayment_dt, next_due_amount_calc_dt)

    def test_next_due_amount_calculation_dt_mid_cycle_a_day_after_due_amount_calculation_day(
        self, mock_get_parameter: MagicMock, mock_get_schedule_time_from_parameters: MagicMock
    ):
        """
        IF effective_dt is not in the opening period
        AND
        IF effective dt is a day after last execution dt, then the expected
        next due amount calculation day is 1 month after last execution dt
        """
        start_dt = datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: 1}
        )
        mock_get_schedule_time_from_parameters.return_value = 2, 3, 4
        last_execution_dt = datetime(2020, 3, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        mock_vault = MagicMock(
            get_account_creation_datetime=MagicMock(return_value=start_dt),
            get_last_execution_datetime=MagicMock(return_value=last_execution_dt),
        )
        effective_dt = datetime(2020, 3, 2, tzinfo=ZoneInfo("UTC"))

        expected_next_repayment_dt = datetime(2020, 4, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        next_due_amount_calc_dt = due_amount_calculation.get_next_due_amount_calculation_datetime(
            vault=mock_vault,
            effective_datetime=effective_dt,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=sentinel.remaining_term,
        )

        self.assertEqual(expected_next_repayment_dt, next_due_amount_calc_dt)

    def test_next_due_amount_calculation_dt_mid_cycle_on_due_amount_calculation_day_after_runtime(
        self, mock_get_parameter: MagicMock, mock_get_schedule_time_from_parameters: MagicMock
    ):
        """
        IF effective_dt is not in the opening period
        AND
        IF effective dt is on the same day but an hour after last execution dt, then the expected
        next due amount calculation day is expected to be 1 month after last execution dt
        """
        start_dt = datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: 1}
        )
        mock_get_schedule_time_from_parameters.return_value = 2, 3, 4
        last_execution_dt = datetime(2020, 3, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        mock_vault = MagicMock(
            get_account_creation_datetime=MagicMock(return_value=start_dt),
            get_last_execution_datetime=MagicMock(return_value=last_execution_dt),
        )
        effective_dt = datetime(2020, 3, 1, 2, 3, 5, tzinfo=ZoneInfo("UTC"))

        expected_next_repayment_dt = datetime(2020, 4, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        next_due_amount_calc_dt = due_amount_calculation.get_next_due_amount_calculation_datetime(
            vault=mock_vault,
            effective_datetime=effective_dt,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=sentinel.remaining_term,
        )

        self.assertEqual(expected_next_repayment_dt, next_due_amount_calc_dt)

    def test_next_due_amount_calc_dt_mid_cycle_on_due_amount_calc_runtime_with_effective_dt(
        self, mock_get_parameter: MagicMock, mock_get_schedule_time_from_parameters: MagicMock
    ):
        """
        IF effective_dt is not in the opening period
        AND
        IF the method is run during the exact due amount calculation dt and effective_dt is passed
        as the last_execution_datetime, then get_next_due_amount_calculation_datetime
        should return a date in the following month.
        """
        start_dt = datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: 1}
        )
        mock_get_schedule_time_from_parameters.return_value = 2, 3, 4
        last_execution_dt = datetime(2020, 2, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        mock_vault = MagicMock(
            get_account_creation_datetime=MagicMock(return_value=start_dt),
            get_last_execution_datetime=MagicMock(return_value=last_execution_dt),
        )
        effective_dt = datetime(2020, 3, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))

        expected_next_repayment_dt = datetime(2020, 3, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        next_due_amount_calc_dt = due_amount_calculation.get_next_due_amount_calculation_datetime(
            vault=mock_vault,
            effective_datetime=effective_dt,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=sentinel.remaining_term,
        )

        self.assertEqual(expected_next_repayment_dt, next_due_amount_calc_dt)

    def test_next_due_amount_calc_dt_on_first_due_calculation_dt(
        self, mock_get_parameter: MagicMock, mock_get_schedule_time_from_parameters: MagicMock
    ):
        """
        IF effective_dt is not in the opening period
        AND
        IF the method is run during the exact due amount calculation dt and last execution dt
        is None, current dt.
        """
        start_dt = datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: 1}
        )
        mock_get_schedule_time_from_parameters.return_value = 2, 3, 4
        mock_vault = MagicMock(
            get_account_creation_datetime=MagicMock(return_value=start_dt),
            get_last_execution_datetime=MagicMock(return_value=None),
        )
        effective_dt = datetime(2020, 2, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))

        expected_next_repayment_dt = datetime(2020, 2, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        next_due_amount_calc_dt = due_amount_calculation.get_next_due_amount_calculation_datetime(
            vault=mock_vault,
            effective_datetime=effective_dt,
            elapsed_term=0,
            remaining_term=sentinel.remaining_term,
        )

        self.assertEqual(expected_next_repayment_dt, next_due_amount_calc_dt)

    def test_next_due_amount_calculation_dt_changed_due_amnt_calc_day_to_after_last_execution_day(
        self, mock_get_parameter: MagicMock, mock_get_schedule_time_from_parameters: MagicMock
    ):
        """
        IF effective_dt is not in the opening period
        AND
        If last execution dt is in the SAME month
        Then, changing the calculation day to a day after effective dt means that the new day
        is reflected in the due amount calculation dt for the next month.
        """
        start_dt = datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: 15}
        )
        mock_get_schedule_time_from_parameters.return_value = 2, 3, 4
        last_execution_dt = datetime(2020, 2, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        mock_vault = MagicMock(
            get_account_creation_datetime=MagicMock(return_value=start_dt),
            get_last_execution_datetime=MagicMock(return_value=last_execution_dt),
        )
        effective_dt = datetime(2020, 2, 10, tzinfo=ZoneInfo("UTC"))

        expected_next_repayment_dt = datetime(2020, 3, 15, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        next_due_amount_calc_dt = due_amount_calculation.get_next_due_amount_calculation_datetime(
            vault=mock_vault,
            effective_datetime=effective_dt,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=sentinel.remaining_term,
        )

        self.assertEqual(expected_next_repayment_dt, next_due_amount_calc_dt)

    def test_next_due_amount_calculation_dt_changed_due_amnt_calc_day_to_before_last_execution_day(
        self, mock_get_parameter: MagicMock, mock_get_schedule_time_from_parameters: MagicMock
    ):
        """
        IF effective_dt is not in the opening period
        AND
        If last execution dt is in the PREVIOUS month
        Then, changing the calculation day to a day after effective dt means that the new day
        is reflected in the due amount calculation dt for the current month.
        """
        start_dt = datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: 2}
        )
        mock_get_schedule_time_from_parameters.return_value = 2, 3, 4
        last_execution_dt = datetime(2020, 2, 15, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        mock_vault = MagicMock(
            get_account_creation_datetime=MagicMock(return_value=start_dt),
            get_last_execution_datetime=MagicMock(return_value=last_execution_dt),
        )
        effective_dt = datetime(2020, 3, 1, tzinfo=ZoneInfo("UTC"))

        expected_next_repayment_dt = datetime(2020, 3, 2, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        next_due_amount_calc_dt = due_amount_calculation.get_next_due_amount_calculation_datetime(
            vault=mock_vault,
            effective_datetime=effective_dt,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=sentinel.remaining_term,
        )

        self.assertEqual(expected_next_repayment_dt, next_due_amount_calc_dt)

    def test_next_due_amount_calculation_dt_changed_due_amnt_calc_to_a_day_before_effective_day(
        self, mock_get_parameter: MagicMock, mock_get_schedule_time_from_parameters: MagicMock
    ):
        """
        IF effective_dt is not in the opening period
        AND
        If last execution dt is in the PREVIOUS month
        Then, changing the calculation day to a day before effective dt means that the new day
        is NOT considered for this month's calculation dt.
        """
        start_dt = datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: 2}
        )
        mock_get_schedule_time_from_parameters.return_value = 2, 3, 4
        last_execution_dt = datetime(2020, 2, 15, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        mock_vault = MagicMock(
            get_account_creation_datetime=MagicMock(return_value=start_dt),
            get_last_execution_datetime=MagicMock(return_value=last_execution_dt),
        )
        effective_dt = datetime(2020, 3, 14, tzinfo=ZoneInfo("UTC"))

        expected_next_repayment_dt = datetime(2020, 3, 15, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        next_due_amount_calc_dt = due_amount_calculation.get_next_due_amount_calculation_datetime(
            vault=mock_vault,
            effective_datetime=effective_dt,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=sentinel.remaining_term,
        )

        self.assertEqual(expected_next_repayment_dt, next_due_amount_calc_dt)

    def test_next_due_amount_calculation_dt_changed_due_amnt_calc_day_applies_from_following_month(
        self, mock_get_parameter: MagicMock, mock_get_schedule_time_from_parameters: MagicMock
    ):
        """
        IF effective_dt is not in the opening period
        AND
        If last execution dt is in the PREVIOUS month
        Then, changing the calculation day to a day before effective dt means that the new day
        is reflected in the due amount calculation dt for the next month only.
        """
        start_dt = datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: 2}
        )
        mock_get_schedule_time_from_parameters.return_value = 2, 3, 4
        last_execution_dt = datetime(2020, 3, 15, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        mock_vault = MagicMock(
            get_account_creation_datetime=MagicMock(return_value=start_dt),
            get_last_execution_datetime=MagicMock(return_value=last_execution_dt),
        )
        effective_dt = datetime(2020, 3, 16, tzinfo=ZoneInfo("UTC"))

        expected_next_repayment_dt = datetime(2020, 4, 2, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        next_due_amount_calc_dt = due_amount_calculation.get_next_due_amount_calculation_datetime(
            vault=mock_vault,
            effective_datetime=effective_dt,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=sentinel.remaining_term,
        )

        self.assertEqual(expected_next_repayment_dt, next_due_amount_calc_dt)

    def test_next_due_amount_calculation_after_loan_term(
        self, mock_get_parameter: MagicMock, mock_get_schedule_time_from_parameters: MagicMock
    ):
        """
        If effective_dt is after the final due amount calculation event, it should return the
        last execution datetime
        """
        start_dt = datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: 1}
        )
        mock_get_schedule_time_from_parameters.return_value = 2, 3, 4
        last_execution_dt = datetime(2021, 2, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        mock_vault = MagicMock(
            get_account_creation_datetime=MagicMock(return_value=start_dt),
            get_last_execution_datetime=MagicMock(return_value=last_execution_dt),
        )
        effective_dt = datetime(2021, 4, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))

        next_due_amount_calc_dt = due_amount_calculation.get_next_due_amount_calculation_datetime(
            vault=mock_vault,
            effective_datetime=effective_dt,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=0,
        )

        self.assertEqual(last_execution_dt, next_due_amount_calc_dt)
        mock_get_parameter.assert_not_called()

    def test_next_due_amount_calculation_effective_datetime_less_than_last_execution(
        self, mock_get_parameter: MagicMock, mock_get_schedule_time_from_parameters: MagicMock
    ):
        """
        If effective_dt is before the last_execution_datetime, it should return the next datetime
        anchored from the effective_dt
        """
        start_dt = datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: 15}
        )
        mock_get_schedule_time_from_parameters.return_value = 2, 3, 4
        last_execution_dt = datetime(2021, 2, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        mock_vault = MagicMock(
            get_account_creation_datetime=MagicMock(return_value=start_dt),
            get_last_execution_datetime=MagicMock(return_value=last_execution_dt),
        )
        effective_dt = datetime(2020, 4, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        expected_next_repayment_dt = datetime(2020, 4, 15, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        next_due_amount_calc_dt = due_amount_calculation.get_next_due_amount_calculation_datetime(
            vault=mock_vault,
            effective_datetime=effective_dt,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=sentinel.remaining_term,
        )

        self.assertEqual(expected_next_repayment_dt, next_due_amount_calc_dt)


class DueAmountCalculationDayChanged(DueAmountCalculationTest):
    def test_due_amount_calculation_day_changed_with_changed_day(self):
        self.assertTrue(
            due_amount_calculation._due_amount_calculation_day_changed(
                last_execution_datetime=datetime(2020, 3, 15, 2, 3, 4, tzinfo=ZoneInfo("UTC")),
                due_amount_calculation_day=1,
            )
        )

    def test_due_amount_calculation_day_changed_with_no_last_execution_dt(self):
        self.assertFalse(
            due_amount_calculation._due_amount_calculation_day_changed(
                last_execution_datetime=None,
                due_amount_calculation_day=15,
            )
        )


@patch.object(due_amount_calculation, "get_next_due_amount_calculation_datetime")
class GetNextRepaymentDateDerivedParamTest(DueAmountCalculationTest):
    def test_get_actual_next_repayment_date_for_param_updated_multiple_times_edge_case(
        self, mock_get_next_due_amount_calculation_datetime: MagicMock
    ):
        """
        When the following is true:
            the due calculation day param has been updated thrice since the last execution
            first and second returned value of next_due_calc_datetime is before the
                effective_datetime and it is eq to last_execution_datetime + 1 month
            the previous param value was updated after last_execution_datetime
        Then:
            get_next_due_amount_calculation_datetime must be rerun passing in the previous due calc
            day param value
        """
        effective_dt = datetime(2020, 3, 19, 13, 3, 5, tzinfo=ZoneInfo("UTC"))
        last_execution_dt = datetime(2020, 2, 5, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        first_next_due_calc_datetime = last_execution_dt + relativedelta(months=1)
        second_next_due_calc_datetime = last_execution_dt + relativedelta(months=1)
        third_next_due_calc_datetime = effective_dt + relativedelta(days=1)
        mock_get_next_due_amount_calculation_datetime.side_effect = [
            first_next_due_calc_datetime,
            second_next_due_calc_datetime,
            third_next_due_calc_datetime,
        ]
        parameter_timeseries = ParameterTimeseries(
            iterable=[
                (
                    datetime(2020, 1, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
                    sentinel.start_due_calc_day,
                ),
                (
                    datetime(2020, 2, 6, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
                    sentinel.previous_2_due_calc_day,
                ),
                (
                    datetime(2020, 2, 7, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
                    sentinel.previous_1_due_calc_day,
                ),
                (
                    datetime(2020, 3, 19, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
                    sentinel.newest_due_calc_day,
                ),
            ]
        )
        mock_param_timeseries = MagicMock(all=MagicMock(return_value=parameter_timeseries))
        mock_vault = MagicMock(
            get_last_execution_datetime=MagicMock(return_value=last_execution_dt),
            get_parameter_timeseries=MagicMock(return_value=mock_param_timeseries),
        )
        result = due_amount_calculation.get_actual_next_repayment_date(
            vault=mock_vault,
            effective_datetime=effective_dt,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=sentinel.remaining_term,
        )
        self.assertEqual(result, third_next_due_calc_datetime)
        mock_get_next_due_amount_calculation_datetime.assert_has_calls(
            [
                call(
                    vault=mock_vault,
                    effective_datetime=effective_dt,
                    elapsed_term=sentinel.elapsed_term,
                    remaining_term=sentinel.remaining_term,
                ),
                call(
                    vault=mock_vault,
                    effective_datetime=effective_dt,
                    elapsed_term=sentinel.elapsed_term,
                    remaining_term=sentinel.remaining_term,
                    due_amount_calculation_day=sentinel.previous_1_due_calc_day,
                ),
                call(
                    vault=mock_vault,
                    effective_datetime=effective_dt,
                    elapsed_term=sentinel.elapsed_term,
                    remaining_term=sentinel.remaining_term,
                    due_amount_calculation_day=sentinel.previous_2_due_calc_day,
                ),
            ]
        )

    def test_get_actual_next_repayment_date_no_param_updates(
        self, mock_get_next_due_amount_calculation_datetime: MagicMock
    ):
        effective_dt = datetime(2020, 3, 19, 13, 3, 5, tzinfo=ZoneInfo("UTC"))
        last_execution_dt = datetime(2020, 2, 5, 2, 3, 4, tzinfo=ZoneInfo("UTC"))
        first_next_due_calc_datetime = last_execution_dt + relativedelta(months=1)
        mock_get_next_due_amount_calculation_datetime.side_effect = [
            first_next_due_calc_datetime,
            sentinel.second_next_due_calc_datetime,
        ]
        parameter_timeseries = ParameterTimeseries(
            iterable=[
                (
                    datetime(2020, 1, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
                    sentinel.start_due_calc_day,
                ),
            ]
        )
        mock_param_timeseries = MagicMock(all=MagicMock(return_value=parameter_timeseries))
        mock_vault = MagicMock(
            get_last_execution_datetime=MagicMock(return_value=last_execution_dt),
            get_parameter_timeseries=MagicMock(return_value=mock_param_timeseries),
        )
        result = due_amount_calculation.get_actual_next_repayment_date(
            vault=mock_vault,
            effective_datetime=effective_dt,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=sentinel.remaining_term,
        )
        self.assertEqual(result, first_next_due_calc_datetime)
        mock_get_next_due_amount_calculation_datetime.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=effective_dt,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=sentinel.remaining_term,
        )


class SuperviseeLastExecutionEffectiveDatetimeTest(SupervisorDueAmountCalculationTest):
    dummy_event = sentinel.event

    def test_last_execution_date_is_in_past(self):
        last_execution_datetimes = {self.dummy_event: DEFAULT_DATETIME - relativedelta(months=1)}
        mock_main_vault = self.create_supervisee_mock(
            last_execution_datetimes=last_execution_datetimes
        )

        expected = DEFAULT_DATETIME - relativedelta(months=1)

        result = due_amount_calculation.get_supervisee_last_execution_effective_datetime(
            loan_vault=sentinel.loan_vault,
            main_vault=mock_main_vault,
            event_type=self.dummy_event,
            effective_datetime=DEFAULT_DATETIME,
            elapsed_term=1,
        )
        self.assertEqual(result, expected)

    def test_last_execution_date_is_effective_datetime(self):
        last_execution_datetimes = {self.dummy_event: DEFAULT_DATETIME}
        mock_main_vault = self.create_supervisee_mock(
            last_execution_datetimes=last_execution_datetimes
        )

        expected = DEFAULT_DATETIME - relativedelta(months=1)

        result = due_amount_calculation.get_supervisee_last_execution_effective_datetime(
            loan_vault=sentinel.loan_vault,
            main_vault=mock_main_vault,
            event_type=self.dummy_event,
            effective_datetime=DEFAULT_DATETIME,
            elapsed_term=1,
        )
        self.assertEqual(result, expected)

    def test_last_execution_date_does_not_exist(self):
        last_execution_datetimes = {self.dummy_event: None}
        mock_loan_vault = self.create_supervisee_mock(
            creation_date=DEFAULT_DATETIME - relativedelta(days=1),
        )
        mock_main_vault = self.create_supervisee_mock(
            creation_date=DEFAULT_DATETIME - relativedelta(days=2),
            last_execution_datetimes=last_execution_datetimes,
        )

        expected = DEFAULT_DATETIME - relativedelta(days=1)

        result = due_amount_calculation.get_supervisee_last_execution_effective_datetime(
            loan_vault=mock_loan_vault,
            main_vault=mock_main_vault,
            event_type=self.dummy_event,
            effective_datetime=DEFAULT_DATETIME,
            elapsed_term=1,
        )
        self.assertEqual(result, expected)

    def test_elapsed_term_is_zero_with_none_last_execution_dt_gets_loan_account_creation_dt(self):
        last_execution_datetimes = {self.dummy_event: None}
        mock_loan_vault = self.create_supervisee_mock(
            creation_date=DEFAULT_DATETIME - relativedelta(days=1),
        )
        mock_main_vault = self.create_supervisee_mock(
            creation_date=DEFAULT_DATETIME - relativedelta(days=2),
            last_execution_datetimes=last_execution_datetimes,
        )

        expected = DEFAULT_DATETIME - relativedelta(days=1)

        result = due_amount_calculation.get_supervisee_last_execution_effective_datetime(
            loan_vault=mock_loan_vault,
            main_vault=mock_main_vault,
            event_type=self.dummy_event,
            effective_datetime=DEFAULT_DATETIME,
            elapsed_term=0,
        )
        self.assertEqual(result, expected)

    def test_elapsed_term_is_zero_with_a_last_execution_dt_gets_loan_account_creation_dt(self):
        last_execution_datetimes = {self.dummy_event: DEFAULT_DATETIME}
        mock_loan_vault = self.create_supervisee_mock(
            creation_date=DEFAULT_DATETIME - relativedelta(days=1),
        )
        mock_main_vault = self.create_supervisee_mock(
            creation_date=DEFAULT_DATETIME - relativedelta(days=2),
            last_execution_datetimes=last_execution_datetimes,
        )

        expected = DEFAULT_DATETIME - relativedelta(days=1)

        result = due_amount_calculation.get_supervisee_last_execution_effective_datetime(
            loan_vault=mock_loan_vault,
            main_vault=mock_main_vault,
            event_type=self.dummy_event,
            effective_datetime=DEFAULT_DATETIME,
            elapsed_term=0,
        )
        self.assertEqual(result, expected)
