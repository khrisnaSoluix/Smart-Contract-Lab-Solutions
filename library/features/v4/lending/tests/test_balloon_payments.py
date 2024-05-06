# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.v4.lending.balloon_payments as balloon_payments

# testing lib
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
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DATETIME,
    FeatureTest,
    construct_parameter_timeseries,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    CustomInstruction,
    ScheduledEvent,
    ScheduleExpression,
    SmartContractEventType,
    UpdateAccountEventTypeDirective,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelPosting,
    SentinelScheduleExpression,
)

# set up feature references
no_repayment = balloon_payments.no_repayment
due_amount_calculation = balloon_payments.due_amount_calculation
lending_parameters = balloon_payments.lending_parameters


class BalloonPaymentTest(FeatureTest):
    maxDiff = None

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


class ScheduleEventsTest(BalloonPaymentTest):
    def test_balloon_payment_event_types(self):
        # run function
        event_types = balloon_payments.event_types(product_name="product_a")
        # validate results
        self.assertListEqual(
            event_types,
            [
                SmartContractEventType(
                    name="BALLOON_PAYMENT_EVENT",
                    scheduler_tag_ids=["PRODUCT_A_BALLOON_PAYMENT_EVENT_AST"],
                )
            ],
        )

    @patch.object(balloon_payments.utils, "get_parameter")
    @patch.object(balloon_payments, "ScheduledEvent")
    @patch.object(balloon_payments.due_amount_calculation, "scheduled_events")
    def test_non_no_repayment_amortisation_returns_due_amount_and_balloon_payment_schedules(
        self,
        mock_due_amount_scheduled_events: MagicMock,
        mock_scheduled_event: MagicMock,
        mock_get_parameters: MagicMock,
    ):
        # expected values
        amortisation_method = "Not a No Repayment Loan"
        account_opening_day = datetime(2020, 1, 2, 3, 4, 5, tzinfo=ZoneInfo("UTC"))

        # construct mocks
        mock_vault = sentinel.vault
        mock_schedule = sentinel.monthly_scheduled_event
        mock_scheduled_event.return_value = mock_schedule
        mock_due_amount_scheduled_events.return_value = {
            due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: mock_schedule
        }

        expected = {
            balloon_payments.BALLOON_PAYMENT_EVENT: mock_schedule,
            due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: mock_schedule,
        }

        # run function
        scheduled_events = balloon_payments.scheduled_events(
            vault=mock_vault,
            account_opening_datetime=account_opening_day,
            amortisation_method=amortisation_method,
        )

        # validate results
        self.assertDictEqual(scheduled_events, expected)

    @patch.object(balloon_payments.utils, "get_parameter")
    @patch.object(balloon_payments.utils, "one_off_schedule_expression")
    @patch.object(balloon_payments, "set_time_from_due_amount_parameter")
    def test_no_repayment_amortisation_returns_one_off_schedule(
        self,
        mock_due_calc_parameter_datetime_offset: MagicMock,
        mock_one_off_schedule_expression: MagicMock,
        mock_get_parameters: MagicMock,
    ):
        # expected value
        amortisation_method = no_repayment.AMORTISATION_METHOD
        account_opening_day = datetime(2020, 1, 2, 3, 4, 5, tzinfo=ZoneInfo("UTC"))
        loan_start_day = account_opening_day + relativedelta(days=1)
        term_months = 10
        mock_due_calc_parameter_datetime_offset.return_value = (
            sentinel.balloon_payment_event_datetime
        )

        expected_one_off_expression_date = account_opening_day + relativedelta(months=10, days=5)
        # construct mocks
        mock_vault = sentinel.vault
        mock_one_off_schedule_expression.return_value = SentinelScheduleExpression(
            "balloon payment"
        )
        mock_get_parameters.side_effect = mock_utils_get_parameter(
            parameters={
                lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: term_months,
                balloon_payments.PARAM_BALLOON_PAYMENT_DAYS_DELTA: 5,
            },
        )
        expected = {
            balloon_payments.BALLOON_PAYMENT_EVENT: ScheduledEvent(
                start_datetime=loan_start_day,
                expression=SentinelScheduleExpression("balloon payment"),
                skip=False,
            ),
            due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: ScheduledEvent(
                start_datetime=loan_start_day,
                expression=balloon_payments.utils.END_OF_TIME_EXPRESSION,
                skip=True,
            ),
        }

        # run function
        scheduled_events = balloon_payments.scheduled_events(
            vault=mock_vault,
            account_opening_datetime=account_opening_day,
            amortisation_method=amortisation_method,
        )

        # validate results
        self.assertDictEqual(scheduled_events, expected)
        mock_one_off_schedule_expression.assert_called_once_with(
            sentinel.balloon_payment_event_datetime
        )
        mock_due_calc_parameter_datetime_offset.assert_called_once_with(
            vault=mock_vault, from_datetime=expected_one_off_expression_date
        )


@patch.object(balloon_payments.utils, "get_parameter")
@patch.object(balloon_payments.utils, "one_off_schedule_expression")
@patch.object(
    balloon_payments.utils, "END_OF_TIME_EXPRESSION", SentinelScheduleExpression("end_of_time")
)
@patch.object(balloon_payments, "set_time_from_due_amount_parameter")
class UpdateBalloonPaymentScheduleTest(BalloonPaymentTest):
    def test_update_balloon_payment_schedule_applies_delta(
        self,
        mock_due_calc_parameter_datetime_offset: MagicMock,
        mock_one_off_schedule_expression: MagicMock,
        mock_get_parameters: MagicMock,
    ):
        # expected value
        effective_timestamp = datetime(2020, 1, 2, 3, 4, 5, tzinfo=ZoneInfo("UTC"))
        expected_one_off_expression_date = datetime(2020, 1, 7, 3, 4, 5, tzinfo=ZoneInfo("UTC"))
        # construct mocks
        mock_vault = sentinel.vault

        end_of_time_expression = SentinelScheduleExpression("end_of_time")
        one_off_expression = SentinelScheduleExpression("one_off")
        mock_one_off_schedule_expression.return_value = one_off_expression
        mock_due_calc_parameter_datetime_offset.return_value = sentinel.balloon_event_datetime
        mock_get_parameters.side_effect = mock_utils_get_parameter(
            parameters={
                balloon_payments.PARAM_BALLOON_PAYMENT_DAYS_DELTA: 5,
            },
        )
        expected = [
            UpdateAccountEventTypeDirective(
                event_type=balloon_payments.BALLOON_PAYMENT_EVENT,
                expression=one_off_expression,
                skip=False,
            ),
            UpdateAccountEventTypeDirective(
                event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                expression=end_of_time_expression,
                skip=True,
            ),
        ]

        # run function
        update_events = balloon_payments.update_balloon_payment_schedule(
            vault=mock_vault,
            execution_timestamp=effective_timestamp,
        )

        # validate results
        self.assertListEqual(update_events, expected)
        mock_one_off_schedule_expression.assert_called_once_with(sentinel.balloon_event_datetime)
        mock_due_calc_parameter_datetime_offset.assert_called_once_with(
            vault=mock_vault, from_datetime=expected_one_off_expression_date
        )

    def test_update_balloon_payment_schedule_unset_delta(
        self,
        mock_due_calc_parameter_datetime_offset: MagicMock,
        mock_one_off_schedule_expression: MagicMock,
        mock_get_parameters: MagicMock,
    ):
        # expected value
        effective_timestamp = datetime(2020, 1, 2, 3, 4, 5, tzinfo=ZoneInfo("UTC"))
        expected_one_off_expression_date = datetime(2020, 1, 2, 3, 4, 5, tzinfo=ZoneInfo("UTC"))
        # construct mocks
        mock_vault = sentinel.vault

        end_of_time_expression = SentinelScheduleExpression("end_of_time")
        one_off_expression = SentinelScheduleExpression("one_off")
        mock_one_off_schedule_expression.return_value = one_off_expression
        mock_due_calc_parameter_datetime_offset.return_value = sentinel.balloon_event_datetime

        mock_get_parameters.side_effect = mock_utils_get_parameter(
            parameters={
                balloon_payments.PARAM_BALLOON_PAYMENT_DAYS_DELTA: 0,
            },
        )
        expected = [
            UpdateAccountEventTypeDirective(
                event_type=balloon_payments.BALLOON_PAYMENT_EVENT,
                expression=one_off_expression,
                skip=False,
            ),
            UpdateAccountEventTypeDirective(
                event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                expression=end_of_time_expression,
                skip=True,
            ),
        ]

        # run function
        update_events = balloon_payments.update_balloon_payment_schedule(
            vault=mock_vault,
            execution_timestamp=effective_timestamp,
        )

        # validate results
        self.assertListEqual(update_events, expected)
        mock_one_off_schedule_expression.assert_called_once_with(sentinel.balloon_event_datetime)
        mock_due_calc_parameter_datetime_offset.assert_called_once_with(
            vault=mock_vault, from_datetime=expected_one_off_expression_date
        )


sentinel_instruction_details = {
    "description": "Updating due balances for final balloon payment.",
    "event": sentinel.event_type,
    "gl_impacted": "True",
    "account_type": sentinel.account_type,
}


@patch.object(balloon_payments.utils, "get_parameter")
@patch.object(
    balloon_payments.due_amount_calculation,
    "get_principal",
    MagicMock(return_value=sentinel.principal),
)
@patch.object(balloon_payments.due_amount_calculation, "transfer_principal_due")
class BalloonPaymentScheduledCodeTest(BalloonPaymentTest):
    @patch.object(
        balloon_payments.no_repayment, "is_no_repayment_loan", MagicMock(return_value=True)
    )
    def test_scheduled_event_hook_with_no_interest_application_feature(
        self,
        mock_transfer_principal_due: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                balloon_payments.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                    BalancesObservation(balances=self.balances, value_datetime=DEFAULT_DATETIME)
                )
            }
        )

        due_postings = [SentinelPosting("principal_due")]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination, "amortisation_method": "no_repayment"}
        )
        mock_transfer_principal_due.return_value = due_postings

        expected_postings = [
            CustomInstruction(
                postings=due_postings,
                override_all_restrictions=True,
                instruction_details=sentinel_instruction_details,
            )
        ]

        postings = balloon_payments.schedule_logic(
            vault=mock_vault,
            hook_arguments=ScheduledEventHookArguments(
                effective_datetime=DEFAULT_DATETIME,
                event_type=sentinel.event_type,
            ),
            account_type=sentinel.account_type,
        )

        self.assertListEqual(postings, expected_postings)

        mock_transfer_principal_due.assert_called_once_with(
            customer_account=mock_vault.account_id,
            principal_due=sentinel.principal,
            denomination=sentinel.denomination,
        )

    @patch.object(
        balloon_payments.no_repayment, "is_no_repayment_loan", MagicMock(return_value=True)
    )
    def test_scheduled_event_hook_with_interest_application_feature(
        self,
        mock_transfer_principal_due: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                balloon_payments.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                    BalancesObservation(balances=self.balances, value_datetime=DEFAULT_DATETIME)
                )
            }
        )
        principal_postings = [SentinelPosting("principal_due")]
        interest_postings = [SentinelPosting("interest_due")]
        mock_interest = MagicMock()
        mock_interest.apply_interest = MagicMock(return_value=interest_postings)
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination, "amortisation_method": "no_repayment"}
        )
        mock_transfer_principal_due.return_value = principal_postings

        expected_postings = [
            CustomInstruction(
                postings=principal_postings + interest_postings,
                override_all_restrictions=True,
                instruction_details=sentinel_instruction_details,
            )
        ]

        postings = balloon_payments.schedule_logic(
            vault=mock_vault,
            hook_arguments=ScheduledEventHookArguments(
                effective_datetime=DEFAULT_DATETIME,
                event_type=sentinel.event_type,
            ),
            account_type=sentinel.account_type,
            interest_application_feature=mock_interest,
        )

        self.assertListEqual(postings, expected_postings)

        mock_transfer_principal_due.assert_called_once_with(
            customer_account=mock_vault.account_id,
            principal_due=sentinel.principal,
            denomination=sentinel.denomination,
        )

    @patch.object(
        balloon_payments.no_repayment, "is_no_repayment_loan", MagicMock(return_value=False)
    )
    def test_scheduled_event_hook_with_unsupported_amortisation_returns_no_postings(
        self,
        mock_transfer_principal_due: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_vault = self.create_mock()

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination, "amortisation_method": "other"}
        )

        postings = balloon_payments.schedule_logic(
            vault=mock_vault,
            hook_arguments=ScheduledEventHookArguments(
                effective_datetime=DEFAULT_DATETIME,
                event_type=sentinel.event_type,
            ),
            account_type=sentinel.account_type,
        )

        self.assertListEqual(postings, [])

        mock_transfer_principal_due.assert_not_called()

    @patch.object(
        balloon_payments.no_repayment, "is_no_repayment_loan", MagicMock(return_value=True)
    )
    def test_scheduled_event_hook_with_no_postings_returns_no_custom_instruction(
        self,
        mock_transfer_principal_due: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                balloon_payments.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                    BalancesObservation(balances=self.balances, value_datetime=DEFAULT_DATETIME)
                )
            }
        )
        mock_interest = MagicMock()
        mock_interest.apply_interest = MagicMock(return_value=[])
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination, "amortisation_method": "no_repayment"}
        )
        mock_transfer_principal_due.return_value = []

        expected_postings: list[Any] = []

        postings = balloon_payments.schedule_logic(
            vault=mock_vault,
            hook_arguments=ScheduledEventHookArguments(
                effective_datetime=DEFAULT_DATETIME,
                event_type=sentinel.event_type,
            ),
            account_type=sentinel.account_type,
            interest_application_feature=mock_interest,
        )

        self.assertEqual(postings, expected_postings)

        mock_transfer_principal_due.assert_called_once_with(
            customer_account=mock_vault.account_id,
            principal_due=sentinel.principal,
            denomination=sentinel.denomination,
        )


@patch.object(balloon_payments.utils, "balance_at_coordinates")
@patch.object(balloon_payments.utils, "get_parameter")
class ExpectedBalloonPaymentAmountTest(BalloonPaymentTest):
    def test_no_repayment_returns_principal(self, mock_get_parameter, mock_balance_coords):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "amortisation_method": "no_repayment",
                "principal": sentinel.principal,
                "denomination": sentinel.denomination,
            }
        )
        mock_balance_coords.return_value = sentinel.principal

        resp = balloon_payments.get_expected_balloon_payment_amount(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.balances,
            interest_rate_feature=sentinel.interest_rate,
        )

        self.assertEqual(resp, sentinel.principal)

    def test_no_repayment_returns_non_negative_zero_principal(
        self, mock_get_parameter, mock_balance_coords
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "amortisation_method": "no_repayment",
                "principal": Decimal("-0.00"),
                "denomination": sentinel.denomination,
            }
        )
        mock_balance_coords.return_value = Decimal("-0.00")

        resp = balloon_payments.get_expected_balloon_payment_amount(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.balances,
            interest_rate_feature=sentinel.interest_rate,
        )

        self.assertEqual(resp, Decimal("0.00"))

    def test_interest_only_returns_principal(self, mock_get_parameter, mock_balance_coords):
        mock_balance_coords.return_value = sentinel.principal
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "amortisation_method": "interest_only",
                "principal": sentinel.principal,
                "denomination": sentinel.denomination,
            }
        )

        resp = balloon_payments.get_expected_balloon_payment_amount(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.balances,
            interest_rate_feature=sentinel.interest_rate,
        )

        self.assertEqual(resp, sentinel.principal)

    def test_no_interest_feature_returns_zero(self, mock_get_parameter, mock_balance_coords):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "amortisation_method": "MINIMUM_REPAYMENT_WITH_BALLOON_PAYMENT",
                balloon_payments.PARAM_BALLOON_PAYMENT_AMOUNT: None,
                balloon_payments.PARAM_BALLOON_EMI_AMOUNT: sentinel.emi,
                "principal": sentinel.principal,
                "denomination": sentinel.denomination,
            }
        )
        mock_balance_coords.return_value = sentinel.principal
        mock_vault = self.create_mock()

        resp = balloon_payments.get_expected_balloon_payment_amount(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            interest_rate_feature=None,
            balances=sentinel.balances,
        )

        self.assertEqual(resp, Decimal("0"))

    def test_minimum_repayment_returns_bp_amount_if_set(
        self, mock_get_parameter, mock_balance_coords
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "amortisation_method": "MINIMUM_REPAYMENT_WITH_BALLOON_PAYMENT",
                "principal": sentinel.principal,
                balloon_payments.PARAM_BALLOON_PAYMENT_AMOUNT: sentinel.balloon_payment_amount,
                balloon_payments.PARAM_BALLOON_EMI_AMOUNT: None,
                "denomination": sentinel.denomination,
            }
        )
        mock_balance_coords.return_value = sentinel.principal
        mock_vault = self.create_mock()
        mock_interest = MagicMock()

        resp = balloon_payments.get_expected_balloon_payment_amount(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            interest_rate_feature=mock_interest,
            balances=sentinel.balances,
        )

        self.assertEqual(resp, sentinel.balloon_payment_amount)

    def test_minimum_repayment_returns_nothing_if_no_emi(
        self, mock_get_parameter, mock_balance_coords
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "amortisation_method": "MINIMUM_REPAYMENT_WITH_BALLOON_PAYMENT",
                "principal": sentinel.principal,
                balloon_payments.PARAM_BALLOON_PAYMENT_AMOUNT: None,
                balloon_payments.PARAM_BALLOON_EMI_AMOUNT: None,
                "denomination": sentinel.denomination,
            }
        )
        mock_vault = self.create_mock()
        mock_interest = MagicMock()
        mock_balance_coords.return_value = sentinel.principal
        resp = balloon_payments.get_expected_balloon_payment_amount(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            interest_rate_feature=mock_interest,
            balances=sentinel.balances,
        )

        self.assertEqual(resp, Decimal("0"))

    @patch.object(balloon_payments, "calculate_lump_sum")
    def test_minimum_repayment_returns_calculated_result(
        self, mock_calculate_lump_sum, mock_get_parameter, mock_balance_coords
    ):
        term_count = Decimal("12")
        precision = Decimal("2")
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "amortisation_method": "MINIMUM_REPAYMENT_WITH_BALLOON_PAYMENT",
                "principal": sentinel.principal,
                balloon_payments.PARAM_BALLOON_PAYMENT_AMOUNT: None,
                balloon_payments.PARAM_BALLOON_EMI_AMOUNT: sentinel.emi,
                lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: term_count,
                "application_precision": precision,
                "denomination": sentinel.denomination,
            }
        )
        mock_balance_coords.return_value = sentinel.principal
        mock_vault = self.create_mock()
        mock_interest = MagicMock()
        mock_interest.get_monthly_interest_rate.return_value = sentinel.rate
        mock_calculate_lump_sum.return_value = sentinel.lump_sum
        resp = balloon_payments.get_expected_balloon_payment_amount(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.balances,
            interest_rate_feature=mock_interest,
        )

        self.assertEqual(resp, sentinel.lump_sum)
        mock_calculate_lump_sum.assert_called_once_with(
            emi=sentinel.emi,
            principal=sentinel.principal,
            rate=sentinel.rate,
            terms=term_count,
            precision=precision,
        )


class DisableBalloonScheduleTest(BalloonPaymentTest):
    @patch.object(
        balloon_payments.utils, "create_end_of_time_schedule", return_value=sentinel.eot_schedule
    )
    def test_disabled_balloon_schedule(self, _):
        resp = balloon_payments.disabled_balloon_schedule(sentinel.datetime)

        self.assertEqual(resp, {balloon_payments.BALLOON_PAYMENT_EVENT: sentinel.eot_schedule})


class CalculateLumpSumTest(BalloonPaymentTest):
    def test_minimum_repayment_loan_emi_amount_3_year_loan(self):
        resp = balloon_payments.calculate_lump_sum(
            emi=Decimal("821"),
            principal=Decimal("100000"),
            rate=Decimal("0.02") / 12,  # Yearly rate -> Monthly Rate
            terms=36,
            precision=2,
        )

        self.assertEqual(resp, Decimal("75743.79"))

    def test_minimum_repayment_loan_emi_amount_1_year_loan(self):
        resp = balloon_payments.calculate_lump_sum(
            emi=Decimal("1850"),
            principal=Decimal("100000"),
            rate=Decimal("0.02") / 12,  # Yearly rate -> Monthly Rate
            terms=12,
            precision=2,
        )

        self.assertEqual(resp, Decimal("79613.80"))


@patch.object(balloon_payments.utils, "get_parameter")
class CalculateBalloonPaymentTopUp(BalloonPaymentTest):
    def test_minimum_repayment_does_not_convert_events(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"amortisation_method": balloon_payments.minimum_repayment.AMORTISATION_METHOD}
        )
        mock_vault = self.create_mock(
            parameter_ts=construct_parameter_timeseries(
                parameter_name_to_value_map={
                    "total_repayment_count": 12,
                },
                default_datetime=DEFAULT_DATETIME,
            )
        )

        resp = balloon_payments.update_no_repayment_balloon_schedule(vault=mock_vault)

        self.assertEqual(resp, {})

    def test_no_repayment_conversion_events(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "amortisation_method": balloon_payments.no_repayment.AMORTISATION_METHOD,
                "total_repayment_count": 24,
                "balloon_payment_days_delta": 0,
                "due_amount_calculation_hour": 1,
                "due_amount_calculation_minute": 2,
                "due_amount_calculation_second": 3,
            }
        )
        mock_vault = self.create_mock()
        expected_schedule_update = {
            balloon_payments.BALLOON_PAYMENT_EVENT: ScheduledEvent(
                expression=ScheduleExpression(
                    year=2021,
                    month=1,
                    day=1,
                    hour=1,
                    minute=2,
                    second=3,
                ),
            ),
        }

        resp = balloon_payments.update_no_repayment_balloon_schedule(
            vault=mock_vault,
        )

        self.assertEqual(resp, expected_schedule_update)

    def test_no_repayment_conversion_events_with_delta(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "amortisation_method": balloon_payments.no_repayment.AMORTISATION_METHOD,
                "total_repayment_count": 24,
                "balloon_payment_days_delta": 15,
                "due_amount_calculation_hour": 1,
                "due_amount_calculation_minute": 2,
                "due_amount_calculation_second": 3,
            }
        )
        mock_vault = self.create_mock()
        expected_schedule_update = {
            balloon_payments.BALLOON_PAYMENT_EVENT: ScheduledEvent(
                expression=ScheduleExpression(
                    year=2021,
                    month=1,
                    day=16,
                    hour=1,
                    minute=2,
                    second=3,
                ),
            )
        }

        resp = balloon_payments.update_no_repayment_balloon_schedule(
            vault=mock_vault,
        )

        self.assertEqual(resp, expected_schedule_update)


class IsBalloonLoanTest(BalloonPaymentTest):
    def test_is_balloon_loan_no_repayment(self):
        self.assertTrue(
            balloon_payments.is_balloon_loan(
                amortisation_method=balloon_payments.no_repayment.AMORTISATION_METHOD
            )
        )

    def test_is_balloon_loan_min_repayment(self):
        self.assertTrue(
            balloon_payments.is_balloon_loan(
                amortisation_method=balloon_payments.minimum_repayment.AMORTISATION_METHOD
            )
        )

    def test_is_balloon_loan_interest_only(self):
        self.assertTrue(
            balloon_payments.is_balloon_loan(
                amortisation_method=balloon_payments.interest_only.AMORTISATION_METHOD
            )
        )

    def test_is_balloon_loan_non_balloon_payment(self):
        self.assertFalse(balloon_payments.is_balloon_loan(amortisation_method="other"))


@patch.object(balloon_payments.utils, "get_parameter")
class OffsettedScheduleEventsTest(BalloonPaymentTest):
    def test_set_time_from_due_amount_parameter(self, mock_get_parameters):
        # Test Params
        test_datetime = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        # Mocks
        mock_get_parameters.side_effect = mock_utils_get_parameter(
            parameters={
                f"{due_amount_calculation.DUE_AMOUNT_CALCULATION_PREFIX}_hour": 5,
                f"{due_amount_calculation.DUE_AMOUNT_CALCULATION_PREFIX}_minute": 10,
                f"{due_amount_calculation.DUE_AMOUNT_CALCULATION_PREFIX}_second": 15,
            },
        )
        mock_vault = self.create_mock()

        # run function
        offsetted_datetime = balloon_payments.set_time_from_due_amount_parameter(
            vault=mock_vault, from_datetime=test_datetime
        )

        # validate results
        self.assertEqual(
            offsetted_datetime, datetime(2019, 1, 1, 5, 10, 15, tzinfo=ZoneInfo("UTC"))
        )

    def test_set_time_from_due_amount_parameter_overwrites_time(self, mock_get_parameters):
        # Test Params
        test_datetime = datetime(2019, 1, 1, 23, 59, 59, tzinfo=ZoneInfo("UTC"))
        # Mocks
        mock_get_parameters.side_effect = mock_utils_get_parameter(
            parameters={
                f"{due_amount_calculation.DUE_AMOUNT_CALCULATION_PREFIX}_hour": 5,
                f"{due_amount_calculation.DUE_AMOUNT_CALCULATION_PREFIX}_minute": 10,
                f"{due_amount_calculation.DUE_AMOUNT_CALCULATION_PREFIX}_second": 15,
            },
        )
        mock_vault = self.create_mock()

        # run function
        offsetted_datetime = balloon_payments.set_time_from_due_amount_parameter(
            vault=mock_vault, from_datetime=test_datetime
        )

        # validate results
        self.assertEqual(
            offsetted_datetime, datetime(2019, 1, 1, 5, 10, 15, tzinfo=ZoneInfo("UTC"))
        )
