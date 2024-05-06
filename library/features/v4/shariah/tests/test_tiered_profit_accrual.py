# standard libs
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.v4.common.utils as utils
import library.features.v4.shariah.tiered_profit_accrual as tiered_profit_accrual
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    FeatureTest,
    construct_parameter_timeseries,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    ScheduledEvent,
    ScheduleExpression,
    SmartContractEventType,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelCustomInstruction,
)

DEFAULT_DATE = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
ACCRUED_PROFIT_PAYABLE_ACCOUNT = sentinel.accrued_profit_payable_account
ACCRUAL_EVENT = tiered_profit_accrual.ACCRUAL_EVENT
ACCRUED_PROFIT_ADDRESS = tiered_profit_accrual.ACCRUED_PROFIT_PAYABLE

EOD_SENTINEL_FETCHER = {"EOD_FETCHER": SentinelBalancesObservation("dummy_observation")}


class TestProfitAccrual(FeatureTest):

    standard_parameters = {
        tiered_profit_accrual.PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT: ACCRUED_PROFIT_PAYABLE_ACCOUNT,
        tiered_profit_accrual.PARAM_ACCRUAL_PRECISION: 5,
        tiered_profit_accrual.PARAM_DAYS_IN_YEAR: "365",
        "denomination": "GBP",
        tiered_profit_accrual.PARAM_TIERED_PROFIT_RATES: {
            sentinel.account_tier: {"0.00": "0.01", "5000.00": "0.05", "10000.00": "0.1"},
        },
    }

    def test_event_types_if_lower_case(self):
        expected_tag_id = ["CURRENT_ACCOUNT_ACCRUE_PROFIT_AST"]
        test_event = {"product_name": "current_account", "expected_tag_id": expected_tag_id}

        result = tiered_profit_accrual.event_types(test_event["product_name"])[0]
        self.assertEqual(result.scheduler_tag_ids, test_event["expected_tag_id"])

    def test_scheduled_events(self):
        parameter_ts = construct_parameter_timeseries(
            parameter_name_to_value_map={
                "profit_accrual_hour": 1,
                "profit_accrual_minute": 2,
                "profit_accrual_second": 3,
            },
            default_datetime=DEFAULT_DATE,
        )
        mock_vault = self.create_mock(parameter_ts=parameter_ts)
        actual_schedules = tiered_profit_accrual.scheduled_events(
            vault=mock_vault, start_datetime=DEFAULT_DATE
        )
        expected_schedules = {
            ACCRUAL_EVENT: ScheduledEvent(
                start_datetime=DEFAULT_DATE,
                expression=ScheduleExpression(hour=1, minute=2, second=3),
            )
        }

        self.assertEqual(actual_schedules, expected_schedules)

    @patch.object(tiered_profit_accrual.utils, "get_parameter")
    @patch.object(tiered_profit_accrual.utils, "sum_balances")
    def test_get_accrual_capital_default_address(
        self, mock_sum_balances: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_sum_balances.side_effect = [Decimal(100)]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": "GBP",
                "accrued_profit_payable_account": ACCRUED_PROFIT_PAYABLE_ACCOUNT,
            }
        )
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                "EOD_FETCHER": SentinelBalancesObservation("eod")
            }
        )
        tiered_profit_accrual.get_accrual_capital(vault=mock_vault, capital_addresses=["DEFAULT"])

        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances_eod, addresses=["DEFAULT"], denomination="GBP"
        )

    @patch.object(tiered_profit_accrual.utils, "get_parameter")
    @patch.object(tiered_profit_accrual.utils, "sum_balances")
    def test_accrue_profit_no_account_tier_rates(
        self, mock_sum_balances: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_sum_balances.return_value = Decimal("2000")
        mock_get_parameter.side_effect = mock_utils_get_parameter(self.standard_parameters)

        mock_vault = self.create_mock(balances_observation_fetchers_mapping=EOD_SENTINEL_FETCHER)

        results = tiered_profit_accrual.accrue_profit(
            vault=mock_vault,
            effective_datetime=datetime(2020, 1, 5, tzinfo=ZoneInfo("UTC")),
            account_tier=sentinel.some_other_tier,
            accrual_address=ACCRUED_PROFIT_ADDRESS,
        )

        self.assertListEqual(results, [])

    @patch.object(tiered_profit_accrual.accruals, "accrual_custom_instruction")
    @patch.object(tiered_profit_accrual.utils, "get_parameter")
    @patch.object(tiered_profit_accrual.utils, "sum_balances")
    def test_accrue_profit_on_lowest_balance_tier_leap_year_actual_days(
        self,
        mock_sum_balances: MagicMock,
        mock_get_parameter: MagicMock,
        mock_accrual_custom_instruction: MagicMock,
    ):
        mock_sum_balances.return_value = Decimal("2000")
        # 2000 * (0.01/366) = 0.05464480874 (5DP)
        expected_profit = Decimal("0.05464")
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {**self.standard_parameters, tiered_profit_accrual.PARAM_DAYS_IN_YEAR: "actual"}
        )
        mock_vault = self.create_mock(balances_observation_fetchers_mapping=EOD_SENTINEL_FETCHER)
        mock_accrual_custom_instruction.return_value = [SentinelCustomInstruction("accrual_ci")]

        results = tiered_profit_accrual.accrue_profit(
            vault=mock_vault,
            effective_datetime=datetime(2020, 1, 5, tzinfo=ZoneInfo("UTC")),
            account_tier=sentinel.account_tier,
            accrual_address=ACCRUED_PROFIT_ADDRESS,
        )
        self.assertListEqual(results, [SentinelCustomInstruction("accrual_ci")])
        mock_accrual_custom_instruction.assert_called_once_with(
            customer_account=mock_vault.account_id,
            customer_address=tiered_profit_accrual.ACCRUED_PROFIT_PAYABLE,
            denomination="GBP",
            amount=expected_profit,
            internal_account=ACCRUED_PROFIT_PAYABLE_ACCOUNT,
            payable=True,
            instruction_details=utils.standard_instruction_details(
                description="Accrual on 2000.00 at annual rate of 1.00%.",
                event_type=ACCRUAL_EVENT,
            ),
        )

    @patch.object(tiered_profit_accrual.accruals, "accrual_custom_instruction")
    @patch.object(tiered_profit_accrual.utils, "get_parameter")
    @patch.object(tiered_profit_accrual.utils, "sum_balances")
    def test_accrue_profit_on_lowest_balance_tier_leap_year_360_days(
        self,
        mock_sum_balances: MagicMock,
        mock_get_parameter: MagicMock,
        mock_accrual_custom_instruction: MagicMock,
    ):
        mock_sum_balances.return_value = Decimal("2000")
        # 2000 * (0.01/360) = 0.05555555555 (5DP)
        expected_profit = Decimal("0.05556")
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {**self.standard_parameters, tiered_profit_accrual.PARAM_DAYS_IN_YEAR: "360"}
        )
        mock_vault = self.create_mock(balances_observation_fetchers_mapping=EOD_SENTINEL_FETCHER)
        mock_accrual_custom_instruction.return_value = [SentinelCustomInstruction("accrual_ci")]

        results = tiered_profit_accrual.accrue_profit(
            vault=mock_vault,
            effective_datetime=datetime(2020, 1, 5, tzinfo=ZoneInfo("UTC")),
            account_tier=sentinel.account_tier,
            accrual_address=ACCRUED_PROFIT_ADDRESS,
        )
        self.assertListEqual(results, [SentinelCustomInstruction("accrual_ci")])
        mock_accrual_custom_instruction.assert_called_once_with(
            customer_account=mock_vault.account_id,
            customer_address=tiered_profit_accrual.ACCRUED_PROFIT_PAYABLE,
            denomination="GBP",
            amount=expected_profit,
            internal_account=ACCRUED_PROFIT_PAYABLE_ACCOUNT,
            payable=True,
            instruction_details=utils.standard_instruction_details(
                description="Accrual on 2000.00 at annual rate of 1.00%.",
                event_type=ACCRUAL_EVENT,
            ),
        )

    @patch.object(tiered_profit_accrual.accruals, "accrual_custom_instruction")
    @patch.object(tiered_profit_accrual.utils, "get_parameter")
    @patch.object(tiered_profit_accrual.utils, "sum_balances")
    def test_accrue_profit_on_middle_balance_tier(
        self,
        mock_sum_balances: MagicMock,
        mock_get_parameter: MagicMock,
        mock_accrual_custom_instruction: MagicMock,
    ):
        mock_sum_balances.return_value = Decimal("7000")
        # (5000 * (0.01/365)) + (2000 * (0.05/365)) = 0.41095890411 (5DP)
        expected_profit = Decimal("0.41096")
        effective_datetime = datetime(2021, 1, 5, tzinfo=ZoneInfo("UTC"))
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {**self.standard_parameters, tiered_profit_accrual.PARAM_DAYS_IN_YEAR: "365"}
        )
        mock_vault = self.create_mock(balances_observation_fetchers_mapping=EOD_SENTINEL_FETCHER)
        mock_accrual_custom_instruction.return_value = [SentinelCustomInstruction("accrual_ci")]
        results = tiered_profit_accrual.accrue_profit(
            vault=mock_vault,
            effective_datetime=effective_datetime,
            account_tier=sentinel.account_tier,
            accrual_address=ACCRUED_PROFIT_ADDRESS,
        )
        self.assertListEqual(results, [SentinelCustomInstruction("accrual_ci")])
        mock_accrual_custom_instruction.assert_called_once_with(
            customer_account=mock_vault.account_id,
            customer_address=tiered_profit_accrual.ACCRUED_PROFIT_PAYABLE,
            denomination="GBP",
            amount=expected_profit,
            internal_account=ACCRUED_PROFIT_PAYABLE_ACCOUNT,
            payable=True,
            instruction_details=utils.standard_instruction_details(
                description="Accrual on 5000.00 at annual rate of 1.00%. "
                "Accrual on 2000.00 at annual rate of 5.00%.",
                event_type=ACCRUAL_EVENT,
            ),
        )

    @patch.object(tiered_profit_accrual.accruals, "accrual_custom_instruction")
    @patch.object(tiered_profit_accrual.utils, "get_parameter")
    @patch.object(tiered_profit_accrual.utils, "sum_balances")
    def test_accrue_profit_on_top_balance_tier(
        self,
        mock_sum_balances: MagicMock,
        mock_get_parameter: MagicMock,
        mock_accrual_custom_instruction: MagicMock,
    ):
        mock_sum_balances.return_value = Decimal("11000")
        # (5000 * (0.01/365)) + (5000 * (0.05/365)) + (1000 * (0.1/365)) = 1.09589041096 (5DP)
        expected_profit = Decimal("1.09589")
        effective_datetime = datetime(2021, 1, 5, tzinfo=ZoneInfo("UTC"))
        mock_get_parameter.side_effect = mock_utils_get_parameter(self.standard_parameters)

        mock_vault = self.create_mock(balances_observation_fetchers_mapping=EOD_SENTINEL_FETCHER)
        mock_accrual_custom_instruction.return_value = [SentinelCustomInstruction("accrual_ci")]

        results = tiered_profit_accrual.accrue_profit(
            vault=mock_vault,
            effective_datetime=effective_datetime,
            account_tier=sentinel.account_tier,
            accrual_address=ACCRUED_PROFIT_ADDRESS,
        )

        self.assertListEqual(results, [SentinelCustomInstruction("accrual_ci")])
        mock_accrual_custom_instruction.assert_called_once_with(
            customer_account=mock_vault.account_id,
            customer_address=tiered_profit_accrual.ACCRUED_PROFIT_PAYABLE,
            denomination="GBP",
            amount=expected_profit,
            internal_account=ACCRUED_PROFIT_PAYABLE_ACCOUNT,
            payable=True,
            instruction_details=utils.standard_instruction_details(
                description="Accrual on 5000.00 at annual rate of 1.00%. "
                "Accrual on 5000.00 at annual rate of 5.00%. "
                "Accrual on 1000.00 at annual rate of 10.00%.",
                event_type=ACCRUAL_EVENT,
            ),
        )

    @patch.object(tiered_profit_accrual.utils, "get_parameter")
    @patch.object(tiered_profit_accrual.utils, "sum_balances")
    def test_accrue_profit_0_accrual(
        self, mock_sum_balances: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_sum_balances.return_value = Decimal("0")
        mock_get_parameter.side_effect = mock_utils_get_parameter(self.standard_parameters)
        mock_vault = self.create_mock(balances_observation_fetchers_mapping=EOD_SENTINEL_FETCHER)

        results = tiered_profit_accrual.accrue_profit(
            vault=mock_vault,
            effective_datetime=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
            account_tier=sentinel.account_tier,
            accrual_address=ACCRUED_PROFIT_ADDRESS,
        )
        self.assertEqual(results, [])

    @patch.object(tiered_profit_accrual.utils, "balance_at_coordinates")
    def test_get_accrued_profit_at(self, mock_balance_at_coordinates: MagicMock):
        mock_balance_at_coordinates.return_value = Decimal("100")

        profit = tiered_profit_accrual.get_accrued_profit(
            balances=sentinel.balances,
            denomination="GBP",
            accrued_profit_address=ACCRUED_PROFIT_ADDRESS,
        )
        self.assertEqual(profit, Decimal("100"))

        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=ACCRUED_PROFIT_ADDRESS,
            denomination="GBP",
        )

    @patch.object(tiered_profit_accrual.accruals, "accrual_custom_instruction")
    @patch.object(tiered_profit_accrual.utils, "get_parameter")
    @patch.object(tiered_profit_accrual.utils, "balance_at_coordinates")
    def test_reverse_profit(
        self,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
        mock_accrual_custom_instruction: MagicMock,
    ):
        mock_balance_at_coordinates.return_value = Decimal("1.5")
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": "GBP",
                tiered_profit_accrual.PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT: (
                    ACCRUED_PROFIT_PAYABLE_ACCOUNT
                ),
            }
        )
        mock_vault = self.create_mock(balances_observation_fetchers_mapping=EOD_SENTINEL_FETCHER)
        mock_accrual_custom_instruction.return_value = [
            SentinelCustomInstruction("reverse_accrual_ci")
        ]
        expected_postings = [SentinelCustomInstruction("reverse_accrual_ci")]

        reversal_postings = tiered_profit_accrual.get_profit_reversal_postings(
            vault=mock_vault,
            accrued_profit_address=ACCRUED_PROFIT_ADDRESS,
            event_name=sentinel.event_name,
            account_type=sentinel.account_type,
        )

        self.assertListEqual(reversal_postings, expected_postings)
        mock_accrual_custom_instruction.assert_called_once_with(
            customer_account=mock_vault.account_id,
            customer_address=ACCRUED_PROFIT_ADDRESS,
            denomination="GBP",
            amount=Decimal("1.5"),
            internal_account=ACCRUED_PROFIT_PAYABLE_ACCOUNT,
            payable=True,
            instruction_details={
                "description": "Reversal of accrued profit of value 1.5 GBP due "
                "to account closure.",
                "event": "sentinel.event_name",
                "gl_impacted": "True",
                "account_type": sentinel.account_type,
            },
            reversal=True,
        )

    @patch.object(tiered_profit_accrual.accruals, "accrual_custom_instruction")
    @patch.object(tiered_profit_accrual.utils, "get_parameter")
    @patch.object(tiered_profit_accrual.utils, "balance_at_coordinates")
    def test_reverse_profit_no_fetching(
        self,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
        mock_accrual_custom_instruction: MagicMock,
    ):
        mock_balance_at_coordinates.return_value = Decimal("1.5")
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                tiered_profit_accrual.PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT: (
                    ACCRUED_PROFIT_PAYABLE_ACCOUNT
                ),
            }
        )
        mock_vault = self.create_mock()
        mock_accrual_custom_instruction.return_value = [
            SentinelCustomInstruction("reverse_accrual_ci")
        ]
        expected_postings = [SentinelCustomInstruction("reverse_accrual_ci")]

        reversal_postings = tiered_profit_accrual.get_profit_reversal_postings(
            vault=mock_vault,
            accrued_profit_address=ACCRUED_PROFIT_ADDRESS,
            event_name=sentinel.event_name,
            account_type=sentinel.account_type,
            denomination=sentinel.denomination_arg,
            balances=sentinel.balances_arg,
        )

        self.assertListEqual(reversal_postings, expected_postings)
        mock_accrual_custom_instruction.assert_called_once_with(
            customer_account=mock_vault.account_id,
            customer_address=ACCRUED_PROFIT_ADDRESS,
            denomination=sentinel.denomination_arg,
            amount=Decimal("1.5"),
            internal_account=ACCRUED_PROFIT_PAYABLE_ACCOUNT,
            payable=True,
            instruction_details={
                "description": "Reversal of accrued profit of value 1.5 sentinel.denomination_arg"
                " due to account closure.",
                "event": "sentinel.event_name",
                "gl_impacted": "True",
                "account_type": sentinel.account_type,
            },
            reversal=True,
        )

    @patch.object(tiered_profit_accrual.accruals, "accrual_custom_instruction")
    @patch.object(tiered_profit_accrual.utils, "get_parameter")
    @patch.object(tiered_profit_accrual.utils, "balance_at_coordinates")
    def test_no_reverse_profit_balance_0(
        self,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
        mock_accrual_custom_instruction: MagicMock,
    ):
        mock_balance_at_coordinates.return_value = Decimal("0")
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": "GBP",
                tiered_profit_accrual.PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT: (
                    ACCRUED_PROFIT_PAYABLE_ACCOUNT
                ),
            }
        )
        mock_vault = self.create_mock(balances_observation_fetchers_mapping=EOD_SENTINEL_FETCHER)

        reversal_postings = tiered_profit_accrual.get_profit_reversal_postings(
            vault=mock_vault,
            accrued_profit_address=ACCRUED_PROFIT_ADDRESS,
            event_name="CLOSE_ACCOUNT",
        )

        self.assertListEqual(reversal_postings, [])
        mock_accrual_custom_instruction.assert_not_called()

    @patch("library.features.v4.common.utils.yearly_to_daily_rate")
    def test_get_daily_profit_rate(self, mock_yearly_to_daily_rate: MagicMock):
        mock_yearly_to_daily_rate.return_value = Decimal("1")

        daily_profit_rate = tiered_profit_accrual.get_daily_profit_rate(
            annual_rate="365",
            days_in_year="365",
            effective_datetime=DEFAULT_DATE,
        )

        self.assertEqual(daily_profit_rate, mock_yearly_to_daily_rate.return_value)

    def test_determine_tier_balance_zero_tier_max_none(self):
        tier_balance = tiered_profit_accrual.determine_tier_balance(effective_balance=Decimal("0"))
        self.assertEqual(tier_balance, Decimal("0"))

    def test_determine_tier_balance_zero_tier_max_signed(self):
        tier_balance = tiered_profit_accrual.determine_tier_balance(
            effective_balance=Decimal("0"), tier_max=Decimal("-0")
        )
        self.assertEqual(tier_balance, Decimal("0"))

    def test_determine_tier_balance_zero_tier_max_valued(self):
        tier_balance = tiered_profit_accrual.determine_tier_balance(
            effective_balance=Decimal("0"), tier_max=Decimal("1")
        )
        self.assertEqual(tier_balance, Decimal("0"))

    def test_determine_tier_balance_zero_tier_max_none_tier_min_signed(self):
        tier_balance = tiered_profit_accrual.determine_tier_balance(
            effective_balance=Decimal("0"), tier_min=Decimal("-1")
        )
        self.assertEqual(tier_balance, Decimal("0"))

    def test_determine_tier_balance_tier_min_greater_than_max_signed(self):
        tier_balance = tiered_profit_accrual.determine_tier_balance(
            effective_balance=Decimal("0"), tier_min=Decimal("-1"), tier_max=Decimal("-2")
        )
        self.assertEqual(tier_balance, Decimal("0"))


class ProfitAccrualScheduleTest(FeatureTest):
    def test_profit_accrual_event_types(self):
        event_types = tiered_profit_accrual.event_types(product_name="product_a")
        self.assertListEqual(
            event_types,
            [
                SmartContractEventType(
                    name=tiered_profit_accrual.ACCRUAL_EVENT,
                    scheduler_tag_ids=[f"PRODUCT_A_{tiered_profit_accrual.ACCRUAL_EVENT}_AST"],
                )
            ],
        )

    @patch.object(tiered_profit_accrual.utils, "daily_scheduled_event")
    def test_profit_accrual_scheduled_event(self, mock_daily_scheduled_event: MagicMock):
        mock_vault = MagicMock()
        mock_daily_scheduled_event.return_value = sentinel.daily_scheduled_event

        scheduled_events = tiered_profit_accrual.scheduled_events(
            vault=mock_vault, start_datetime=sentinel.start_datetime
        )

        self.assertDictEqual(
            scheduled_events,
            {tiered_profit_accrual.ACCRUAL_EVENT: sentinel.daily_scheduled_event},
        )
        mock_daily_scheduled_event.assert_called_once_with(
            vault=mock_vault,
            start_datetime=sentinel.start_datetime,
            parameter_prefix="profit_accrual",
        )
