# standard libs
from collections import defaultdict
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Callable
from unittest.mock import MagicMock, call, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.v4.common.addresses as common_addresses
import library.features.v4.lending.lending_addresses as lending_addresses
import library.features.v4.lending.overpayment_allowance as overpayment_allowance
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import DEFAULT_ASSET, Balance, BalanceCoordinate, BalanceTimeseries, Phase

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    BalanceDefaultDict,
    CustomInstruction,
    ScheduledEvent,
    ScheduleSkip,
    SmartContractEventType,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalance,
    SentinelBalancesObservation,
    SentinelPosting,
    SentinelScheduleExpression,
)

DEFAULT_DATE = datetime(2020, 1, 2, 3, 4, 5, 6, tzinfo=ZoneInfo("UTC"))

OVERPAYMENT_COORDINATE = BalanceCoordinate(
    account_address=overpayment_allowance.overpayment.OVERPAYMENT,
    asset=DEFAULT_ASSET,
    denomination=sentinel.denomination,
    phase=Phase.COMMITTED,
)

PRINCIPAL_COORDINATE = BalanceCoordinate(
    account_address=lending_addresses.PRINCIPAL,
    asset=DEFAULT_ASSET,
    denomination=sentinel.denomination,
    phase=Phase.COMMITTED,
)


class OverpaymentTest(FeatureTest):
    maxDiff = None


class EventTypesTest(FeatureTest):
    def test_event_types(self):
        self.assertListEqual(
            overpayment_allowance.event_types(account_type="some_account"),
            [
                SmartContractEventType(
                    name=overpayment_allowance.CHECK_OVERPAYMENT_ALLOWANCE_EVENT,
                    scheduler_tag_ids=[
                        f"SOME_ACCOUNT_{overpayment_allowance.CHECK_OVERPAYMENT_ALLOWANCE_EVENT}"
                        "_AST"
                    ],
                )
            ],
        )


@patch.object(overpayment_allowance.utils, "get_schedule_expression_from_parameters")
class ScheduledEventsTest(FeatureTest):
    def test_scheduled_event_runs_on_yearly_basis(
        self, mock_get_schedule_expression_from_parameters: MagicMock
    ):

        sentinel_expression = SentinelScheduleExpression("handle_allowance")
        mock_get_schedule_expression_from_parameters.return_value = sentinel_expression

        scheduled_events = overpayment_allowance.scheduled_events(
            vault=sentinel.vault, allowance_period_start_datetime=DEFAULT_DATE
        )

        self.assertDictEqual(
            scheduled_events,
            {
                overpayment_allowance.CHECK_OVERPAYMENT_ALLOWANCE_EVENT: ScheduledEvent(
                    start_datetime=datetime(2021, 1, 1, 23, 59, 59, tzinfo=ZoneInfo("UTC")),
                    expression=sentinel_expression,
                )
            },
        )

        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=sentinel.vault,
            parameter_prefix=overpayment_allowance.CHECK_OVERPAYMENT_ALLOWANCE_PREFIX,
            day=2,
            month=1,
        )


class HandleAllowanceHelpersTest(FeatureTest):
    @patch.object(overpayment_allowance.utils, "round_decimal")
    @patch.object(overpayment_allowance.utils, "balance_at_coordinates")
    def test_get_allowance_for_period(
        self, mock_balance_at_coordinates: MagicMock, mock_round_decimal: MagicMock
    ):
        mock_balance_at_coordinates.return_value = Decimal("1000")
        mock_round_decimal.return_value = sentinel.rounded_allowance

        self.assertEqual(
            overpayment_allowance.get_allowance_for_period(
                start_of_period_balances=sentinel.balances,
                allowance_percentage=Decimal("0.05"),
                denomination=sentinel.denomination,
            ),
            sentinel.rounded_allowance,
        )

        mock_round_decimal.assert_called_once_with(amount=Decimal("50"), decimal_places=2)

    @patch.object(overpayment_allowance.utils, "balance_at_coordinates")
    def test_get_allowance_usage(self, mock_balance_at_coordinates: MagicMock):
        mock_balance_at_coordinates.side_effect = (
            lambda balances, address, denomination: Decimal("100")
            if balances == sentinel.start_of_period_balances
            else Decimal("200")
        )

        self.assertEqual(
            overpayment_allowance.get_allowance_usage(
                start_of_period_balances=sentinel.start_of_period_balances,
                end_of_period_balances=sentinel.end_of_period_balances,
                denomination=sentinel.denomination,
            ),
            Decimal("100"),
        )

        mock_balance_at_coordinates.assert_has_calls(
            [
                call(
                    balances=sentinel.end_of_period_balances,
                    address=overpayment_allowance.overpayment.OVERPAYMENT,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=sentinel.start_of_period_balances,
                    address=overpayment_allowance.overpayment.OVERPAYMENT,
                    denomination=sentinel.denomination,
                ),
            ]
        )

    @patch.object(overpayment_allowance.utils, "balance_at_coordinates")
    def test_get_allowance_usage_at_least_0(self, mock_balance_at_coordinates: MagicMock):
        mock_balance_at_coordinates.side_effect = (
            lambda balances, address, denomination: Decimal("100")
            if balances == sentinel.start_of_period_balances
            else Decimal("0")
        )

        self.assertEqual(
            overpayment_allowance.get_allowance_usage(
                start_of_period_balances=sentinel.start_of_period_balances,
                end_of_period_balances=sentinel.end_of_period_balances,
                denomination=sentinel.denomination,
            ),
            Decimal("0"),
        )

    @patch.object(overpayment_allowance.utils, "round_decimal")
    def test_get_allowance_fee(self, mock_round_decimal: MagicMock):
        mock_round_decimal.return_value = sentinel.rounded_fee

        self.assertEqual(
            overpayment_allowance.get_allowance_usage_fee(
                allowance=Decimal("0"),
                used_allowance=Decimal("1"),
                overpayment_allowance_fee_percentage=Decimal("0.01"),
            ),
            sentinel.rounded_fee,
        )

        mock_round_decimal.assert_called_once_with(Decimal("0.01"), decimal_places=2)

    @patch.object(overpayment_allowance.utils, "round_decimal")
    def test_get_allowance_fee_zero_if_allowance_not_exceeded(self, mock_round_decimal: MagicMock):

        self.assertEqual(
            overpayment_allowance.get_allowance_usage_fee(
                allowance=Decimal("1"),
                used_allowance=Decimal("0"),
                overpayment_allowance_fee_percentage=Decimal("0.01"),
            ),
            Decimal("0"),
        )

        mock_round_decimal.assert_not_called()


@patch.object(overpayment_allowance.utils, "standard_instruction_details")
@patch.object(overpayment_allowance.utils, "get_parameter")
@patch.object(overpayment_allowance.fees, "fee_custom_instruction")
@patch.object(overpayment_allowance, "get_allowance_usage_fee")
@patch.object(overpayment_allowance, "get_allowance_usage")
@patch.object(overpayment_allowance, "get_allowance_for_period")
@patch.object(overpayment_allowance, "set_overpayment_allowance_for_period")
class HandleAllowanceUsageTest(FeatureTest):

    standard_params = mock_utils_get_parameter(
        parameters={
            "denomination": sentinel.denomination,
            overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_PERCENTAGE: (
                sentinel.overpayment_percentage
            ),
            overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE: (
                sentinel.allowance_fee_percentage
            ),
            overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT: (
                sentinel.allowance_fee_income_account
            ),
        }
    )

    @patch.object(overpayment_allowance.utils, "balance_at_coordinates")
    def test_allowance_fee_charged(
        self,
        mock_balance_at_coordinates: MagicMock,
        mock_set_overpayment_allowance_for_period: MagicMock,
        mock_get_allowance_for_period: MagicMock,
        mock_get_allowance_usage: MagicMock,
        mock_get_allowance_usage_fee: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_get_allowance_for_period.return_value = sentinel.allowance
        mock_get_allowance_usage.return_value = sentinel.used_allowance
        mock_get_allowance_usage_fee.return_value = sentinel.allowance_fee
        mock_fee_custom_instruction.return_value = [sentinel.fee_custom_instruction]
        mock_balance_at_coordinates.return_value = (
            sentinel.remaining_overpayment_allowance_tracker_balance
        )
        mock_set_overpayment_allowance_for_period.return_value = [
            sentinel.set_overpayment_allowance
        ]
        mock_standard_instruction_details.return_value = {"sentinel": "details"}
        mock_get_parameter.side_effect = (
            mock_get_parameter.side_effect
        ) = HandleAllowanceUsageTest.standard_params
        eod_observation = SentinelBalancesObservation("eod")
        one_year_observation = SentinelBalancesObservation("one_year")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                overpayment_allowance.EOD_OVERPAYMENT_ALLOWANCE_FETCHER_ID: (  # type: ignore
                    eod_observation
                ),
                overpayment_allowance.ONE_YEAR_OVERPAYMENT_ALLOWANCE_FETCHER_ID: (  # type: ignore
                    one_year_observation
                ),
            }
        )

        result = overpayment_allowance.handle_allowance_usage(mock_vault, sentinel.account_type)

        self.assertListEqual(
            result, [sentinel.set_overpayment_allowance, sentinel.fee_custom_instruction]
        )

        mock_get_allowance_for_period.assert_has_calls(
            [
                call(
                    start_of_period_balances=sentinel.balances_eod,
                    allowance_percentage=sentinel.overpayment_percentage,
                    denomination=sentinel.denomination,
                ),
                call(
                    start_of_period_balances=sentinel.balances_one_year,
                    allowance_percentage=sentinel.overpayment_percentage,
                    denomination=sentinel.denomination,
                ),
            ]
        )
        mock_get_allowance_usage.assert_called_once_with(
            start_of_period_balances=sentinel.balances_one_year,
            end_of_period_balances=sentinel.balances_eod,
            denomination=sentinel.denomination,
        )
        mock_get_allowance_usage_fee.assert_called_once_with(
            used_allowance=sentinel.used_allowance,
            allowance=sentinel.allowance,
            overpayment_allowance_fee_percentage=sentinel.allowance_fee_percentage,
        )
        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=mock_vault.account_id,
            denomination=sentinel.denomination,
            amount=sentinel.allowance_fee,
            internal_account=sentinel.allowance_fee_income_account,
            customer_account_address=overpayment_allowance.lending_addresses.PENALTIES,
            instruction_details={"sentinel": "details"},
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances_eod,
            address=overpayment_allowance.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
            denomination=sentinel.denomination,
        )
        mock_set_overpayment_allowance_for_period.assert_called_once_with(
            current_overpayment_allowance=sentinel.remaining_overpayment_allowance_tracker_balance,
            updated_overpayment_allowance=sentinel.allowance,
            denomination=sentinel.denomination,
            account_id=mock_vault.account_id,
        )

    @patch.object(overpayment_allowance, "get_start_of_current_allowance_period")
    def test_allowance_fee_charged_adhoc(
        self,
        mock_get_start_of_current_allowance_period: MagicMock,
        mock_set_overpayment_allowance_for_period: MagicMock,
        mock_get_allowance_for_period: MagicMock,
        mock_get_allowance_usage: MagicMock,
        mock_get_allowance_usage_fee: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        start_of_period = datetime(2020, 1, 2, 3, 4, 5, 6, tzinfo=ZoneInfo("UTC"))
        effective_datetime = datetime(2020, 4, 5, 6, 7, 8, 9, tzinfo=ZoneInfo("UTC"))

        mock_get_allowance_for_period.return_value = sentinel.allowance
        mock_get_allowance_usage.return_value = sentinel.used_allowance
        mock_get_allowance_usage_fee.return_value = sentinel.allowance_fee
        mock_fee_custom_instruction.return_value = [sentinel.fee_custom_instruction]
        mock_set_overpayment_allowance_for_period.return_value = []
        mock_standard_instruction_details.return_value = {"sentinel": "details"}
        mock_get_parameter.side_effect = HandleAllowanceUsageTest.standard_params
        mock_get_start_of_current_allowance_period.return_value = start_of_period
        overpayment_balance_ts = BalanceTimeseries(
            [
                (start_of_period, SentinelBalance("start_of_period_overpayment")),
                (effective_datetime, SentinelBalance("effective_datetime_overpayment")),
            ]
        )

        principal_balance_ts = BalanceTimeseries(
            [
                (start_of_period, SentinelBalance("start_of_period_principal")),
                (effective_datetime, SentinelBalance("effective_datetime_principal")),
            ]
        )

        expected_start_of_period_balances = BalanceDefaultDict(
            mapping={
                OVERPAYMENT_COORDINATE: SentinelBalance("start_of_period_overpayment"),
                PRINCIPAL_COORDINATE: SentinelBalance("start_of_period_principal"),
            }
        )
        expected_end_of_period_balances = BalanceDefaultDict(
            mapping={
                OVERPAYMENT_COORDINATE: SentinelBalance("effective_datetime_overpayment"),
                PRINCIPAL_COORDINATE: SentinelBalance("effective_datetime_principal"),
            }
        )

        balances_interval_fetchers_mapping = {
            overpayment_allowance.ONE_YEAR_OVERPAYMENT_ALLOWANCE_INTERVAL_FETCHER_ID: defaultdict(
                None,
                {
                    OVERPAYMENT_COORDINATE: overpayment_balance_ts,
                    PRINCIPAL_COORDINATE: principal_balance_ts,
                },
            )
        }

        mock_vault = self.create_mock(
            balances_interval_fetchers_mapping=balances_interval_fetchers_mapping,
            last_execution_datetimes={
                overpayment_allowance.CHECK_OVERPAYMENT_ALLOWANCE_EVENT: sentinel.last_exec_time
            },
        )

        result = overpayment_allowance.handle_allowance_usage_adhoc(
            vault=mock_vault,
            account_type=sentinel.account_type,
            effective_datetime=effective_datetime,
        )

        self.assertListEqual(result, [sentinel.fee_custom_instruction])

        mock_get_start_of_current_allowance_period.assert_called_once_with(
            effective_datetime=effective_datetime,
            account_creation_datetime=mock_vault.get_account_creation_datetime(),
            check_overpayment_allowance_last_execution_datetime=sentinel.last_exec_time,
        )
        mock_get_allowance_for_period.assert_called_once_with(
            start_of_period_balances=expected_start_of_period_balances,
            allowance_percentage=sentinel.overpayment_percentage,
            denomination=sentinel.denomination,
        )
        mock_get_allowance_usage.assert_called_once_with(
            start_of_period_balances=expected_start_of_period_balances,
            end_of_period_balances=expected_end_of_period_balances,
            denomination=sentinel.denomination,
        )
        mock_get_allowance_usage_fee.assert_called_once_with(
            used_allowance=sentinel.used_allowance,
            allowance=sentinel.allowance,
            overpayment_allowance_fee_percentage=sentinel.allowance_fee_percentage,
        )
        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=mock_vault.account_id,
            denomination=sentinel.denomination,
            amount=sentinel.allowance_fee,
            internal_account=sentinel.allowance_fee_income_account,
            customer_account_address=overpayment_allowance.lending_addresses.PENALTIES,
            instruction_details={"sentinel": "details"},
        )


class StartOfAllowancePeriodTest(FeatureTest):
    def test_start_of_allowance_period_when_handle_allowance_schedule_has_run(self):

        last_execution_datetime = datetime(2023, 1, 2, 3, 4, 5, 6, tzinfo=ZoneInfo("UTC"))
        expected = datetime(2023, 1, 2, tzinfo=ZoneInfo("UTC"))

        self.assertEqual(
            overpayment_allowance.get_start_of_current_allowance_period(
                effective_datetime=sentinel.effective_datetime,
                account_creation_datetime=sentinel.account_creation_datetime,
                check_overpayment_allowance_last_execution_datetime=last_execution_datetime,
            ),
            expected,
        )

    def test_start_of_allowance_period_when_effective_date_gt_1_year_after_account_creation(self):

        effective_datetime = datetime(2023, 1, 2, 3, 4, 5, 6, tzinfo=ZoneInfo("UTC"))
        account_creation_datetime = effective_datetime - relativedelta(years=2)
        expected = datetime(2022, 1, 2, tzinfo=ZoneInfo("UTC"))

        self.assertEqual(
            overpayment_allowance.get_start_of_current_allowance_period(
                effective_datetime=effective_datetime,
                account_creation_datetime=account_creation_datetime,
                check_overpayment_allowance_last_execution_datetime=None,
            ),
            expected,
        )

    def test_start_of_allowance_period_when_effective_date_eq_1_year_after_account_creation(
        self,
    ):

        effective_datetime = datetime(2023, 1, 2, 3, 4, 5, 6, tzinfo=ZoneInfo("UTC"))
        account_creation_datetime = effective_datetime - relativedelta(years=1)
        expected = account_creation_datetime

        self.assertEqual(
            overpayment_allowance.get_start_of_current_allowance_period(
                effective_datetime=effective_datetime,
                account_creation_datetime=account_creation_datetime,
                check_overpayment_allowance_last_execution_datetime=None,
            ),
            expected,
        )

    def test_start_of_allowance_period_when_effective_date_lt_1_year_after_account_creation(self):

        effective_datetime = datetime(2023, 1, 2, 3, 4, 5, 6, tzinfo=ZoneInfo("UTC"))
        account_creation_datetime = effective_datetime - relativedelta(months=2)
        expected = account_creation_datetime

        self.assertEqual(
            overpayment_allowance.get_start_of_current_allowance_period(
                effective_datetime=effective_datetime,
                account_creation_datetime=account_creation_datetime,
                check_overpayment_allowance_last_execution_datetime=None,
            ),
            expected,
        )


class OverpaymentAllowanceStatusTest(FeatureTest):
    @patch.object(overpayment_allowance.utils, "get_parameter")
    @patch.object(overpayment_allowance, "get_start_of_current_allowance_period")
    @patch.object(overpayment_allowance, "get_allowance")
    def test_overpayment_allowance_status(
        self,
        mock_get_allowance: MagicMock,
        mock_get_start_of_current_allowance_period: MagicMock,
        mock_get_parameter: MagicMock,
    ):

        start_of_period = datetime(2020, 1, 2, 3, 4, 5, 6, tzinfo=ZoneInfo("UTC"))
        effective_datetime = datetime(2020, 4, 5, 6, 7, 8, 9, tzinfo=ZoneInfo("UTC"))

        mock_get_start_of_current_allowance_period.return_value = start_of_period
        mock_get_allowance.return_value = sentinel.allowance
        overpayment_balance_ts = BalanceTimeseries(
            [
                (start_of_period, Balance(net=Decimal("100"))),
                (effective_datetime, Balance(net=Decimal("300"))),
            ]
        )

        principal_balance_ts = BalanceTimeseries(
            [
                (start_of_period, SentinelBalance("start_of_period_principal")),
                (effective_datetime, SentinelBalance("effective_datetime_principal")),
            ]
        )

        # this is the difference between the overpayment balance timeseries items
        expected_allowance_used = Decimal("200")
        expected_allowance = sentinel.allowance

        balances_interval_fetchers_mapping = {
            overpayment_allowance.ONE_YEAR_OVERPAYMENT_ALLOWANCE_INTERVAL_FETCHER_ID: defaultdict(
                None,
                {
                    OVERPAYMENT_COORDINATE: overpayment_balance_ts,
                    PRINCIPAL_COORDINATE: principal_balance_ts,
                },
            )
        }
        mock_vault = self.create_mock(
            balances_interval_fetchers_mapping=balances_interval_fetchers_mapping,
            last_execution_datetimes={
                overpayment_allowance.CHECK_OVERPAYMENT_ALLOWANCE_EVENT: sentinel.last_exec_time
            },
        )

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
                overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_PERCENTAGE: (
                    sentinel.overpayment_percentage
                ),
                overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE: (
                    sentinel.allowance_fee_percentage
                ),
                overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT: (
                    sentinel.allowance_fee_income_account
                ),
            }
        )

        self.assertEqual(
            overpayment_allowance.get_overpayment_allowance_status(
                vault=mock_vault, effective_datetime=effective_datetime
            ),
            (expected_allowance, expected_allowance_used),
        )

        mock_get_start_of_current_allowance_period.assert_called_once_with(
            effective_datetime=effective_datetime,
            account_creation_datetime=mock_vault.get_account_creation_datetime(),
            check_overpayment_allowance_last_execution_datetime=sentinel.last_exec_time,
        )
        mock_get_allowance.assert_called_once_with(
            principal=sentinel.net_start_of_period_principal,
            allowance_percentage=sentinel.overpayment_percentage,
        )


@patch.object(overpayment_allowance.utils, "create_postings")
class SetOverpaymentAllowanceForPeriodTest(FeatureTest):
    def test_no_postings_to_return_if_overpayment_delta_is_the_same(
        self,
        mock_create_postings: MagicMock,
    ):

        self.assertListEqual(
            overpayment_allowance.set_overpayment_allowance_for_period(
                current_overpayment_allowance=Decimal("100"),
                updated_overpayment_allowance=Decimal("100"),
                denomination=sentinel.denomination,
                account_id=sentinel.account_id,
            ),
            [],
        )

        mock_create_postings.assert_not_called()

    def test_positive_overpayment_allowance_delta_returns_correct_ci(
        self,
        mock_create_postings: MagicMock,
    ):

        mock_create_postings.return_value = [SentinelPosting("overpayment_allowance")]

        self.assertListEqual(
            overpayment_allowance.set_overpayment_allowance_for_period(
                current_overpayment_allowance=Decimal("150"),
                updated_overpayment_allowance=Decimal("100"),
                denomination=sentinel.denomination,
                account_id=sentinel.account_id,
            ),
            [
                CustomInstruction(
                    postings=[SentinelPosting("overpayment_allowance")],
                    instruction_details={
                        "description": "Resetting the overpayment allowance tracker balance",
                        "event": "RESET_REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER",
                    },
                )
            ],
        )

        mock_create_postings.assert_called_once_with(
            amount=Decimal("50"),
            debit_account=sentinel.account_id,
            credit_account=sentinel.account_id,
            debit_address=common_addresses.INTERNAL_CONTRA,
            credit_address=overpayment_allowance.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
            denomination=sentinel.denomination,
        )

    def test_negative_overpayment_allowance_delta_returns_correct_ci(
        self,
        mock_create_postings: MagicMock,
    ):

        mock_create_postings.return_value = [SentinelPosting("overpayment_allowance")]

        self.assertListEqual(
            overpayment_allowance.set_overpayment_allowance_for_period(
                current_overpayment_allowance=Decimal("100"),
                updated_overpayment_allowance=Decimal("150"),
                denomination=sentinel.denomination,
                account_id=sentinel.account_id,
            ),
            [
                CustomInstruction(
                    postings=[SentinelPosting("overpayment_allowance")],
                    instruction_details={
                        "description": "Resetting the overpayment allowance tracker balance",
                        "event": "RESET_REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER",
                    },
                )
            ],
        )

        mock_create_postings.assert_called_once_with(
            amount=Decimal("50"),
            debit_account=sentinel.account_id,
            credit_account=sentinel.account_id,
            debit_address=overpayment_allowance.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
            credit_address=common_addresses.INTERNAL_CONTRA,
            denomination=sentinel.denomination,
        )


@patch.object(overpayment_allowance.utils, "balance_at_coordinates")
@patch.object(overpayment_allowance.utils, "create_postings")
class ReduceOverpaymentAllowanceTest(FeatureTest):
    def test_no_postings_when_overpayment_amount_is_negative(
        self,
        mock_create_postings: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):

        # outstanding principal on loan
        mock_balance_at_coordinates.return_value = Decimal("100000")

        self.assertListEqual(
            overpayment_allowance.reduce_overpayment_allowance(
                vault=sentinel.vault,
                overpayment_amount=Decimal("-10"),
                denomination=sentinel.denomination,
                balances=sentinel.balances,
            ),
            [],
        )

        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=lending_addresses.PRINCIPAL,
            denomination=sentinel.denomination,
        )
        mock_create_postings.assert_not_called()

    def test_no_postings_when_overpayment_amount_is_0(
        self,
        mock_create_postings: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):

        # outstanding principal on loan
        mock_balance_at_coordinates.return_value = Decimal("100000")

        self.assertListEqual(
            overpayment_allowance.reduce_overpayment_allowance(
                vault=sentinel.vault,
                overpayment_amount=Decimal("0"),
                denomination=sentinel.denomination,
                balances=sentinel.balances,
            ),
            [],
        )

        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=lending_addresses.PRINCIPAL,
            denomination=sentinel.denomination,
        )
        mock_create_postings.assert_not_called()

    def test_no_postings_when_total_outstanding_principal_is_0(
        self,
        mock_create_postings: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):

        # outstanding principal on loan
        mock_balance_at_coordinates.return_value = Decimal("0")

        self.assertListEqual(
            overpayment_allowance.reduce_overpayment_allowance(
                vault=sentinel.vault,
                overpayment_amount=Decimal("10"),
                denomination=sentinel.denomination,
                balances=sentinel.balances,
            ),
            [],
        )

        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=lending_addresses.PRINCIPAL,
            denomination=sentinel.denomination,
        )
        mock_create_postings.assert_not_called()

    def test_return_postings_to_decrease_overpayment_allowance(
        self,
        mock_create_postings: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):

        # outstanding principal on loan
        mock_balance_at_coordinates.return_value = Decimal("100000")
        mock_create_postings.return_value = [sentinel.postings]
        mock_vault = self.create_mock()

        self.assertListEqual(
            overpayment_allowance.reduce_overpayment_allowance(
                vault=mock_vault,
                overpayment_amount=Decimal("10"),
                denomination=sentinel.denomination,
                balances=sentinel.balances,
            ),
            [sentinel.postings],
        )

        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=lending_addresses.PRINCIPAL,
            denomination=sentinel.denomination,
        )
        mock_create_postings.assert_called_once_with(
            amount=Decimal("10"),
            debit_account=mock_vault.account_id,
            debit_address=common_addresses.INTERNAL_CONTRA,
            credit_account=mock_vault.account_id,
            credit_address=overpayment_allowance.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
            denomination=sentinel.denomination,
        )


@patch.object(overpayment_allowance.utils, "sum_balances")
@patch.object(overpayment_allowance.utils, "balance_at_coordinates")
@patch.object(overpayment_allowance.utils, "round_decimal")
@patch.object(overpayment_allowance.utils, "get_parameter")
class GetOverpaymentAllowanceFeeForEarlyRepaymentTest(FeatureTest):
    def mock_sum_balances(self, address_name_to_amount_mapping: dict[str, Decimal]) -> Callable:
        outstanding_addresses = lending_addresses.ALL_OUTSTANDING
        repayment_addresses = lending_addresses.REPAYMENT_HIERARCHY

        def sum_balances(balances: BalanceDefaultDict, addresses: list[str], denomination: str):
            if addresses == outstanding_addresses:
                return address_name_to_amount_mapping["ALL_OUTSTANDING"]
            elif addresses == repayment_addresses:
                return address_name_to_amount_mapping["REPAYMENT_HIERARCHY"]

        return sum_balances

    def test_overpayment_allowance_covers_early_repayment_amount_exactly(
        self,
        mock_get_parameter: MagicMock,
        mock_round_decimal: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_sum_balances: MagicMock,
    ):

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE: Decimal("0.01")
            }
        )
        mock_sum_balances.side_effect = self.mock_sum_balances(
            {"ALL_OUTSTANDING": Decimal("5000"), "REPAYMENT_HIERARCHY": Decimal("2000")}
        )
        # the balance of the overpayment allowance tracker
        mock_balance_at_coordinates.return_value = Decimal("3000")
        mock_round_decimal.return_value = Decimal("0")

        self.assertEqual(
            overpayment_allowance.get_overpayment_allowance_fee_for_early_repayment(
                vault=sentinel.vault,
                denomination=sentinel.denomination,
                balances=sentinel.balances,
            ),
            Decimal("0"),
        )
        mock_get_parameter.assert_called_once_with(
            vault=sentinel.vault,
            name=overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE,
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=overpayment_allowance.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
            denomination=sentinel.denomination,
        )
        mock_round_decimal.assert_called_once_with(
            amount=Decimal("0"),
            decimal_places=2,
        )

    def test_overpayment_allowance_exceeds_early_repayment_amount(
        self,
        mock_get_parameter: MagicMock,
        mock_round_decimal: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_sum_balances: MagicMock,
    ):

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE: Decimal("0.01")
            }
        )
        mock_sum_balances.side_effect = self.mock_sum_balances(
            {"ALL_OUTSTANDING": Decimal("5000"), "REPAYMENT_HIERARCHY": Decimal("2000")}
        )
        # the balance of the overpayment allowance tracker
        mock_balance_at_coordinates.return_value = Decimal("4000")
        mock_round_decimal.return_value = Decimal("0")

        self.assertEqual(
            overpayment_allowance.get_overpayment_allowance_fee_for_early_repayment(
                vault=sentinel.vault,
                denomination=sentinel.denomination,
                balances=sentinel.balances,
            ),
            Decimal("0"),
        )
        mock_get_parameter.assert_called_once_with(
            vault=sentinel.vault,
            name=overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE,
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=overpayment_allowance.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
            denomination=sentinel.denomination,
        )
        mock_round_decimal.assert_called_once_with(
            amount=Decimal("0"),
            decimal_places=2,
        )

    def test_overpayment_allowance_is_less_than_early_repayment_amount(
        self,
        mock_get_parameter: MagicMock,
        mock_round_decimal: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_sum_balances: MagicMock,
    ):

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE: Decimal("0.01")
            }
        )

        mock_sum_balances.side_effect = self.mock_sum_balances(
            {"ALL_OUTSTANDING": Decimal("5000"), "REPAYMENT_HIERARCHY": Decimal("2000")}
        )
        # the balance of the overpayment allowance tracker
        mock_balance_at_coordinates.return_value = Decimal("2000")
        mock_round_decimal.return_value = Decimal("10")

        self.assertEqual(
            overpayment_allowance.get_overpayment_allowance_fee_for_early_repayment(
                vault=sentinel.vault,
                denomination=sentinel.denomination,
                balances=sentinel.balances,
            ),
            Decimal("10"),
        )
        mock_get_parameter.assert_called_once_with(
            vault=sentinel.vault,
            name=overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE,
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=overpayment_allowance.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
            denomination=sentinel.denomination,
        )
        mock_round_decimal.assert_called_once_with(
            # 0.01 * 1000
            amount=Decimal("10"),
            decimal_places=2,
        )

    def test_optional_parameters_are_defaulted_correctly(
        self,
        mock_get_parameter: MagicMock,
        mock_round_decimal: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_sum_balances: MagicMock,
    ):

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
                overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE: Decimal("0.01"),
            }
        )

        mock_sum_balances.side_effect = self.mock_sum_balances(
            {"ALL_OUTSTANDING": Decimal("5000"), "REPAYMENT_HIERARCHY": Decimal("2000")}
        )
        # the balance of the overpayment allowance tracker
        mock_balance_at_coordinates.return_value = Decimal("2000")
        mock_round_decimal.return_value = Decimal("10")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                "live_balances_bof": SentinelBalancesObservation("dummy_balances")
            }
        )

        self.assertEqual(
            overpayment_allowance.get_overpayment_allowance_fee_for_early_repayment(
                vault=mock_vault,
            ),
            Decimal("10"),
        )
        mock_get_parameter.assert_has_calls(
            [
                call(
                    vault=mock_vault,
                    name="denomination",
                ),
                call(
                    vault=mock_vault,
                    name=overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE,
                ),
            ]
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances_dummy_balances,
            address=overpayment_allowance.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
            denomination=sentinel.denomination,
        )
        mock_round_decimal.assert_called_once_with(
            # 0.01 * 1000
            amount=Decimal("10"),
            decimal_places=2,
        )


@patch.object(overpayment_allowance.utils, "get_schedule_expression_from_parameters")
class UpdateScheduleEventTest(FeatureTest):
    def test_update_schedule_event(self, mock_get_schedule_expression_from_parameters: MagicMock):
        schedule_expression = SentinelScheduleExpression("overpayment_allowance_expression")
        mock_get_schedule_expression_from_parameters.return_value = schedule_expression
        expected_skip = DEFAULT_DATE.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) + relativedelta(years=1, seconds=-1)

        expected_result = {
            "CHECK_OVERPAYMENT_ALLOWANCE": ScheduledEvent(
                expression=schedule_expression, skip=ScheduleSkip(end=expected_skip)
            )
        }
        result = overpayment_allowance.update_scheduled_event(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATE
        )
        self.assertEqual(expected_result, result)


@patch.object(overpayment_allowance.utils, "get_parameter")
@patch.object(overpayment_allowance, "set_overpayment_allowance_for_period")
class InitialiseOverpaymentAllowanceFromPrincipalAmountTest(FeatureTest):
    def test_sets_allowance_with_denomination(
        self, mock_set_overpayment_allowance_for_period: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_PERCENTAGE: Decimal("0.01")
            }
        )
        mock_set_overpayment_allowance_for_period.return_value = [sentinel.custom_instruction]
        mock_vault = self.create_mock()

        self.assertEqual(
            overpayment_allowance.initialise_overpayment_allowance_from_principal_amount(
                vault=mock_vault, denomination=sentinel.denomination, principal=Decimal("100")
            ),
            [sentinel.custom_instruction],
        )

        mock_get_parameter.assert_called_once_with(
            vault=mock_vault,
            name=overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_PERCENTAGE,
        )
        mock_set_overpayment_allowance_for_period.assert_called_once_with(
            current_overpayment_allowance=Decimal("0"),
            updated_overpayment_allowance=Decimal("1"),
            denomination=sentinel.denomination,
            account_id=mock_vault.account_id,
        )

    def test_sets_allowance_without_denomination(
        self, mock_set_overpayment_allowance_for_period: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
                overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_PERCENTAGE: Decimal("0.01"),
            }
        )
        mock_set_overpayment_allowance_for_period.return_value = [sentinel.custom_instruction]
        mock_vault = self.create_mock()

        self.assertEqual(
            overpayment_allowance.initialise_overpayment_allowance_from_principal_amount(
                vault=mock_vault, principal=Decimal("100")
            ),
            [sentinel.custom_instruction],
        )

        mock_get_parameter.assert_has_calls(
            [
                call(
                    vault=mock_vault,
                    name="denomination",
                ),
                call(
                    vault=mock_vault,
                    name=overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_PERCENTAGE,
                ),
            ]
        )
        mock_set_overpayment_allowance_for_period.assert_called_once_with(
            current_overpayment_allowance=Decimal("0"),
            updated_overpayment_allowance=Decimal("1"),
            denomination=sentinel.denomination,
            account_id=mock_vault.account_id,
        )


@patch.object(overpayment_allowance.utils, "balance_at_coordinates")
@patch.object(overpayment_allowance.utils, "create_postings")
class GetResidualCleanupPostingsTest(FeatureTest):
    def test_negative_overpayment_allowance_amount_returns_correct_postings(
        self, mock_create_postings: MagicMock, mock_balance_at_coordinates: MagicMock
    ):
        # overpayment allowance amount
        mock_balance_at_coordinates.return_value = Decimal("-10")
        mock_create_postings.return_value = [sentinel.postings]

        self.assertEqual(
            overpayment_allowance.get_residual_cleanup_postings(
                balances=sentinel.balances,
                account_id=sentinel.account_id,
                denomination=sentinel.denomination,
            ),
            [sentinel.postings],
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=overpayment_allowance.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
            denomination=sentinel.denomination,
        )
        mock_create_postings.assert_called_once_with(
            amount=Decimal("10"),
            debit_account=sentinel.account_id,
            credit_account=sentinel.account_id,
            debit_address=overpayment_allowance.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
            credit_address=common_addresses.INTERNAL_CONTRA,
            denomination=sentinel.denomination,
        )

    def test_positive_overpayment_allowance_amount_returns_correct_postings(
        self, mock_create_postings: MagicMock, mock_balance_at_coordinates: MagicMock
    ):
        # overpayment allowance amount
        mock_balance_at_coordinates.return_value = Decimal("10")
        mock_create_postings.return_value = [sentinel.postings]

        self.assertEqual(
            overpayment_allowance.get_residual_cleanup_postings(
                balances=sentinel.balances,
                account_id=sentinel.account_id,
                denomination=sentinel.denomination,
            ),
            [sentinel.postings],
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=overpayment_allowance.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
            denomination=sentinel.denomination,
        )
        mock_create_postings.assert_called_once_with(
            amount=Decimal("10"),
            debit_account=sentinel.account_id,
            credit_account=sentinel.account_id,
            debit_address=common_addresses.INTERNAL_CONTRA,
            credit_address=overpayment_allowance.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
            denomination=sentinel.denomination,
        )
