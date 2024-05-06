# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from json import dumps
from unittest.mock import MagicMock, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.v4.deposit.fees.minimum_monthly_balance as minimum_monthly_balance
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DATETIME,
    DEFAULT_DENOMINATION,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    BalanceDefaultDict,
    Phase,
    SmartContractEventType,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelScheduledEvent,
)


class MinimumMonthlyBalanceTest(FeatureTest):
    def test_minimum_balance_fee_event_types(self):
        # mocks
        expected = SmartContractEventType(
            name=minimum_monthly_balance.APPLY_MINIMUM_MONTHLY_BALANCE_EVENT,
            scheduler_tag_ids=[
                f"PRODUCT_{minimum_monthly_balance.APPLY_MINIMUM_MONTHLY_BALANCE_EVENT}_AST"
            ],
        )
        # function call
        result = minimum_monthly_balance.event_types("PRODUCT")
        # assertion
        self.assertListEqual(result, [expected])

    @patch.object(minimum_monthly_balance.utils, "monthly_scheduled_event")
    def test_scheduled_event(self, mock_monthly_scheduled_event: MagicMock):
        # mocks
        expected = {
            minimum_monthly_balance.APPLY_MINIMUM_MONTHLY_BALANCE_EVENT: SentinelScheduledEvent(
                "inactivity_fee_event"
            )
        }
        # function call
        mock_monthly_scheduled_event.return_value = SentinelScheduledEvent("inactivity_fee_event")
        result = minimum_monthly_balance.scheduled_events(
            vault=sentinel.vault, start_datetime=sentinel.datetime
        )
        # assertion
        self.assertDictEqual(result, expected)
        mock_monthly_scheduled_event.assert_called_once_with(
            vault=sentinel.vault,
            start_datetime=sentinel.datetime,
            parameter_prefix=minimum_monthly_balance.MINIMUM_BALANCE_FEE_PREFIX,
        )


class MinimumMonthlyBalanceFeeApplicationTest(FeatureTest):
    def balances(
        self,
        default_committed: Decimal = Decimal("0"),
        default_pending_outgoing: Decimal = Decimal("0"),
        default_pending_incoming: Decimal = Decimal("0"),
    ) -> BalanceDefaultDict:
        mapping = {
            self.balance_coordinate(denomination=DEFAULT_DENOMINATION): self.balance(
                net=default_committed
            ),
            self.balance_coordinate(phase=Phase.PENDING_OUT): self.balance(
                net=default_pending_outgoing
            ),
            self.balance_coordinate(phase=Phase.PENDING_IN): self.balance(
                net=default_pending_incoming
            ),
        }
        return BalanceDefaultDict(mapping=mapping)

    @patch.object(minimum_monthly_balance.utils, "get_parameter")
    @patch.object(minimum_monthly_balance.utils, "balance_at_coordinates")
    @patch.object(minimum_monthly_balance.utils, "average_balance")
    @patch.object(
        minimum_monthly_balance.account_tiers, "get_tiered_parameter_value_based_on_account_tier"
    )
    def test_fee_not_applied_when_mean_balance_above_threshold(
        self,
        mock_get_tiered_parameter_value_based_on_account_tier: MagicMock,
        mock_average_balance: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        effective_time = datetime(2020, 2, 1, tzinfo=ZoneInfo("UTC"))
        period_start = effective_time - relativedelta(months=1)
        num_days = (effective_time.date() - period_start.date()).days

        test_balance_observation_fetcher_mapping = {}

        for i in range(num_days):
            test_balance_observation_fetcher_mapping[
                f"PREVIOUS_EOD_{i+1}_FETCHER_ID"
            ] = SentinelBalancesObservation("dummy_observation")

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=test_balance_observation_fetcher_mapping,
            creation_date=datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
        )
        mock_balance_at_coordinates.side_effect = [Decimal("150") for _ in range(num_days)]
        mock_average_balance.side_effect = [Decimal("150")]
        mock_get_tiered_parameter_value_based_on_account_tier.side_effect = [Decimal("100")]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "account_tier_names": dumps(["Z"]),
                "minimum_balance_threshold_by_tier": dumps({"Z": "100"}),
                "minimum_balance_fee": Decimal("20"),
                "minimum_balance_fee_income_account": "MINIMUM_BALANCE_FEE_INCOME",
                "partial_minimum_balance_fee_application_enabled": False,
            }
        )

        self.assertListEqual(
            minimum_monthly_balance.apply_minimum_balance_fee(
                vault=mock_vault,
                denomination=DEFAULT_DENOMINATION,
                effective_datetime=effective_time,
            ),
            [],
        )

    @patch.object(minimum_monthly_balance.utils, "get_parameter")
    @patch.object(
        minimum_monthly_balance.account_tiers, "get_tiered_parameter_value_based_on_account_tier"
    )
    def test_fee_not_applied_when_threshold_is_zero(
        self,
        mock_get_tiered_parameter_value_based_on_account_tier: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        effective_time = datetime(2020, 2, 1, tzinfo=ZoneInfo("UTC"))
        mock_vault = self.create_mock()
        mock_get_tiered_parameter_value_based_on_account_tier.side_effect = [Decimal("0")]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "account_tier_names": dumps(["Z"]),
                "minimum_balance_threshold_by_tier": dumps({"Z": "0"}),
                "minimum_balance_fee": Decimal("20"),
            }
        )

        self.assertListEqual(
            minimum_monthly_balance.apply_minimum_balance_fee(
                vault=mock_vault,
                denomination=DEFAULT_DENOMINATION,
                effective_datetime=effective_time,
            ),
            [],
        )

    @patch.object(minimum_monthly_balance.utils, "get_parameter")
    @patch.object(minimum_monthly_balance.utils, "balance_at_coordinates")
    @patch.object(minimum_monthly_balance.utils, "average_balance")
    @patch.object(
        minimum_monthly_balance.account_tiers, "get_tiered_parameter_value_based_on_account_tier"
    )
    @patch.object(minimum_monthly_balance.fees, "fee_custom_instruction")
    def test_fee_applied_when_mean_balance_below_threshold(
        self,
        mock_fee_custom_instruction: MagicMock,
        mock_get_tiered_parameter_value_based_on_account_tier: MagicMock,
        mock_average_balance: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        effective_time = datetime(2020, 2, 1, tzinfo=ZoneInfo("UTC"))
        period_start = effective_time - relativedelta(months=1)
        num_days = (effective_time.date() - period_start.date()).days
        test_balance_observation_fetcher_mapping = {}

        for i in range(num_days):
            test_balance_observation_fetcher_mapping[
                f"PREVIOUS_EOD_{i+1}_FETCHER_ID"
            ] = SentinelBalancesObservation("dummy_observation")

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=test_balance_observation_fetcher_mapping,
            creation_date=datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
        )
        mock_balance_at_coordinates.side_effect = [Decimal("50") for _ in range(num_days)]
        mock_average_balance.side_effect = [Decimal("50")]
        mock_get_tiered_parameter_value_based_on_account_tier.side_effect = [Decimal("100")]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": DEFAULT_DENOMINATION,
                "account_tier_names": dumps(["Z"]),
                "minimum_balance_threshold_by_tier": dumps({"Z": "100"}),
                "minimum_balance_fee": Decimal("20"),
                "minimum_balance_fee_income_account": "MINIMUM_BALANCE_FEE_INCOME",
                "partial_minimum_balance_fee_application_enabled": False,
            }
        )
        mock_fee_custom_instruction_response = [sentinel.fee_custom_instruction]
        mock_fee_custom_instruction.side_effect = [mock_fee_custom_instruction_response]

        fee_postings = minimum_monthly_balance.apply_minimum_balance_fee(
            vault=mock_vault,
            effective_datetime=effective_time,
        )

        mock_average_balance.assert_called_once_with(
            balances=[Decimal("50") for _ in range(num_days - 1)]
        )
        mock_fee_custom_instruction.assert_called_once_with(
            instruction_details={
                "description": "Minimum balance fee",
                "event": "APPLY_MINIMUM_BALANCE_FEE",
            },
            internal_account="MINIMUM_BALANCE_FEE_INCOME",
            denomination=DEFAULT_DENOMINATION,
            customer_account_id="default_account",
            amount=Decimal("20"),
        )
        self.assertEqual(fee_postings, mock_fee_custom_instruction_response)

    @patch.object(minimum_monthly_balance.utils, "get_parameter")
    @patch.object(minimum_monthly_balance.utils, "balance_at_coordinates")
    @patch.object(minimum_monthly_balance.utils, "average_balance")
    @patch.object(
        minimum_monthly_balance.account_tiers, "get_tiered_parameter_value_based_on_account_tier"
    )
    def test_fee_applied_when_mean_balance_equals_threshold_and_period_start_exactly_one_month(
        self,
        mock_get_tiered_parameter_value_based_on_account_tier: MagicMock,
        mock_average_balance: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        effective_time = datetime(2020, 2, 1, 0, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        period_start = effective_time - relativedelta(months=1)
        num_days = (effective_time.date() - period_start.date()).days

        test_balance_observation_fetcher_mapping = {}

        for i in range(num_days):
            test_balance_observation_fetcher_mapping[
                f"PREVIOUS_EOD_{i+1}_FETCHER_ID"
            ] = SentinelBalancesObservation("dummy_observation")

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=test_balance_observation_fetcher_mapping,
            creation_date=period_start,
        )
        mock_balance_at_coordinates.side_effect = [Decimal("100") for _ in range(num_days)]
        mock_average_balance.side_effect = [Decimal("100")]
        mock_get_tiered_parameter_value_based_on_account_tier.side_effect = [Decimal("100")]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "account_tier_names": dumps(["Z"]),
                "minimum_balance_threshold_by_tier": dumps({"Z": "100"}),
                "minimum_balance_fee": Decimal("20"),
                "minimum_balance_fee_income_account": "MINIMUM_BALANCE_FEE_INCOME",
                "partial_minimum_balance_fee_application_enabled": False,
            }
        )

        self.assertListEqual(
            minimum_monthly_balance.apply_minimum_balance_fee(
                vault=mock_vault,
                denomination=DEFAULT_DENOMINATION,
                effective_datetime=effective_time,
            ),
            [],
        )

    @patch.object(minimum_monthly_balance.utils, "get_parameter")
    @patch.object(minimum_monthly_balance.utils, "balance_at_coordinates")
    @patch.object(minimum_monthly_balance.utils, "average_balance")
    @patch.object(
        minimum_monthly_balance.account_tiers, "get_tiered_parameter_value_based_on_account_tier"
    )
    @patch.object(minimum_monthly_balance.fees, "fee_custom_instruction")
    def test_fee_applied_balance_below_threshold_and_period_date_before_creation_date(
        self,
        mock_fee_custom_instruction: MagicMock,
        mock_get_tiered_parameter_value_based_on_account_tier: MagicMock,
        mock_average_balance: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        effective_time = datetime(2020, 2, 28, 0, 1, 0, tzinfo=ZoneInfo("UTC"))
        creation_date = datetime(2020, 1, 31, 14, 30, 33, tzinfo=ZoneInfo("UTC"))
        num_days = (effective_time.date() - creation_date.date()).days
        test_balance_observation_fetcher_mapping = {}

        for i in range(num_days):
            test_balance_observation_fetcher_mapping[
                f"PREVIOUS_EOD_{i+1}_FETCHER_ID"
            ] = SentinelBalancesObservation("dummy_observation")

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=test_balance_observation_fetcher_mapping,
            creation_date=creation_date,
        )
        mock_balance_at_coordinates.side_effect = [Decimal("50") for _ in range(num_days)]
        mock_average_balance.side_effect = [Decimal("50")]
        mock_get_tiered_parameter_value_based_on_account_tier.side_effect = [Decimal("100")]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": DEFAULT_DENOMINATION,
                "account_tier_names": dumps(["Z"]),
                "minimum_balance_threshold_by_tier": dumps({"Z": "100"}),
                "minimum_balance_fee": Decimal("20"),
                "minimum_balance_fee_income_account": "MINIMUM_BALANCE_FEE_INCOME",
                "partial_minimum_balance_fee_application_enabled": False,
            }
        )
        mock_fee_custom_instruction_response = [sentinel.fee_custom_instruction]
        mock_fee_custom_instruction.side_effect = [mock_fee_custom_instruction_response]

        fee_postings = minimum_monthly_balance.apply_minimum_balance_fee(
            vault=mock_vault,
            denomination=DEFAULT_DENOMINATION,
            effective_datetime=effective_time,
        )

        mock_average_balance.assert_called_once_with(
            balances=[Decimal("50") for _ in range(num_days - 1)]
        )
        mock_fee_custom_instruction.assert_called_once_with(
            instruction_details={
                "description": "Minimum balance fee",
                "event": "APPLY_MINIMUM_BALANCE_FEE",
            },
            internal_account="MINIMUM_BALANCE_FEE_INCOME",
            denomination=DEFAULT_DENOMINATION,
            customer_account_id="default_account",
            amount=Decimal("20"),
        )
        self.assertEqual(fee_postings, mock_fee_custom_instruction_response)

    @patch.object(minimum_monthly_balance.utils, "get_parameter")
    @patch.object(minimum_monthly_balance.utils, "balance_at_coordinates")
    @patch.object(minimum_monthly_balance.utils, "average_balance")
    @patch.object(
        minimum_monthly_balance.account_tiers, "get_tiered_parameter_value_based_on_account_tier"
    )
    @patch.object(minimum_monthly_balance.fees, "fee_custom_instruction")
    def test_fee_applied_balance_below_threshold_period_after_creation_date(
        self,
        mock_fee_custom_instruction: MagicMock,
        mock_get_tiered_parameter_value_based_on_account_tier: MagicMock,
        mock_average_balance: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        effective_time = datetime(2020, 2, 28, 0, 1, 0, tzinfo=ZoneInfo("UTC"))
        creation_date = datetime(2018, 1, 31, 14, 30, 33, tzinfo=ZoneInfo("UTC"))
        num_days = (effective_time - (effective_time - relativedelta(months=1))).days
        test_balance_observation_fetcher_mapping = {}

        for i in range(num_days):
            test_balance_observation_fetcher_mapping[
                f"PREVIOUS_EOD_{i+1}_FETCHER_ID"
            ] = SentinelBalancesObservation("dummy_observation")

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=test_balance_observation_fetcher_mapping,
            creation_date=creation_date,
        )
        mock_balance_at_coordinates.side_effect = [Decimal("50") for _ in range(num_days)]
        mock_average_balance.side_effect = [Decimal("50")]
        mock_get_tiered_parameter_value_based_on_account_tier.side_effect = [Decimal("100")]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": DEFAULT_DENOMINATION,
                "account_tier_names": dumps(["Z"]),
                "minimum_balance_threshold_by_tier": dumps({"Z": "100"}),
                "minimum_balance_fee": Decimal("20"),
                "minimum_balance_fee_income_account": "MINIMUM_BALANCE_FEE_INCOME",
                "partial_minimum_balance_fee_application_enabled": False,
            }
        )
        mock_fee_custom_instruction_response = [sentinel.fee_custom_instruction]
        mock_fee_custom_instruction.side_effect = [mock_fee_custom_instruction_response]

        fee_postings = minimum_monthly_balance.apply_minimum_balance_fee(
            vault=mock_vault,
            denomination=DEFAULT_DENOMINATION,
            effective_datetime=effective_time,
        )

        mock_average_balance.assert_called_once_with(
            balances=[Decimal("50") for _ in range(num_days)]
        )
        mock_fee_custom_instruction.assert_called_once_with(
            instruction_details={
                "description": "Minimum balance fee",
                "event": "APPLY_MINIMUM_BALANCE_FEE",
            },
            internal_account="MINIMUM_BALANCE_FEE_INCOME",
            denomination=DEFAULT_DENOMINATION,
            customer_account_id="default_account",
            amount=Decimal("20"),
        )
        self.assertEqual(fee_postings, mock_fee_custom_instruction_response)


@patch.object(minimum_monthly_balance.partial_fee, "charge_partial_fee")
@patch.object(minimum_monthly_balance.fees, "fee_custom_instruction")
@patch.object(minimum_monthly_balance.utils, "get_parameter")
@patch.object(minimum_monthly_balance, "_is_monthly_mean_balance_above_threshold")
class PartialMinimumMonthlyBalanceFeeApplicationTest(FeatureTest):
    def test_minimum_balance_fee_partially_applied_with_fee_instructions_optional_args_provided(
        self,
        mock_is_monthly_mean_balance_above_threshold: MagicMock,
        mock_get_parameter: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_charge_partial_fee: MagicMock,
    ):
        mock_is_monthly_mean_balance_above_threshold.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "minimum_balance_fee": Decimal("20"),
                "minimum_balance_fee_income_account": "MINIMUM_BALANCE_FEE_INCOME",
                "partial_minimum_balance_fee_application_enabled": True,
            }
        )
        mock_fee_custom_instruction.return_value = [sentinel.fee_custom_instruction]
        mock_charge_partial_fee.return_value = [sentinel.partial_fee_custom_instruction]

        mock_vault = self.create_mock()

        result = minimum_monthly_balance.apply_minimum_balance_fee(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=sentinel.denomination,
            balances=sentinel.balances,
            available_balance_feature=sentinel.available_balance,
        )
        self.assertListEqual(result, [sentinel.partial_fee_custom_instruction])
        mock_charge_partial_fee.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            fee_custom_instruction=sentinel.fee_custom_instruction,
            fee_details=minimum_monthly_balance.PARTIAL_FEE_DETAILS,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            available_balance_feature=sentinel.available_balance,
        )

    def test_minimum_balance_fee_partially_applied_with_fee_instructions_optional_args_not_provided(
        self,
        mock_is_monthly_mean_balance_above_threshold: MagicMock,
        mock_get_parameter: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_charge_partial_fee: MagicMock,
    ):
        mock_is_monthly_mean_balance_above_threshold.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "minimum_balance_fee": Decimal("20"),
                "minimum_balance_fee_income_account": "MINIMUM_BALANCE_FEE_INCOME",
                "partial_minimum_balance_fee_application_enabled": True,
                "denomination": "GBP",
            }
        )
        mock_fee_custom_instruction.return_value = [sentinel.fee_custom_instruction]
        mock_charge_partial_fee.return_value = [sentinel.partial_fee_custom_instruction]

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                minimum_monthly_balance.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(  # noqa: E501
                    "effective"
                )
            }
        )

        result = minimum_monthly_balance.apply_minimum_balance_fee(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            available_balance_feature=sentinel.available_balance,
        )
        self.assertListEqual(result, [sentinel.partial_fee_custom_instruction])
        mock_charge_partial_fee.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            fee_custom_instruction=sentinel.fee_custom_instruction,
            fee_details=minimum_monthly_balance.PARTIAL_FEE_DETAILS,
            denomination="GBP",
            balances=sentinel.balances_effective,
            available_balance_feature=sentinel.available_balance,
        )

    def test_minimum_balance_fee_partially_applied_when_partial_fee_enabled_no_fee_instructions(
        self,
        mock_is_monthly_mean_balance_above_threshold: MagicMock,
        mock_get_parameter: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_charge_partial_fee: MagicMock,
    ):
        mock_is_monthly_mean_balance_above_threshold.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "minimum_balance_fee": Decimal("20"),
                "minimum_balance_fee_income_account": "MINIMUM_BALANCE_FEE_INCOME",
                "partial_minimum_balance_fee_application_enabled": True,
            }
        )
        mock_fee_custom_instruction.return_value = []

        mock_vault = self.create_mock()

        result = minimum_monthly_balance.apply_minimum_balance_fee(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )
        self.assertListEqual(result, [])
        mock_charge_partial_fee.assert_not_called()
