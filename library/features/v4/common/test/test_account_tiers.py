# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from decimal import Decimal
from json import dumps, loads
from zoneinfo import ZoneInfo

# features
import library.features.v4.common.account_tiers as account_tiers

# contracts api
from contracts_api import FlagTimeseries

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    FeatureTest,
    construct_flag_timeseries,
    construct_parameter_timeseries,
)

DEFAULT_DATETIME = datetime(2021, 1, 1, tzinfo=ZoneInfo("UTC"))

ACCOUNT_TIER_NAMES = dumps(
    [
        "TIER_UPPER",
        "TIER_MIDDLE",
        "TIER_LOWER",
    ]
)

MIN_BALANCE_THRESHOLD_TIERS = {"TIER_UPPER": "100", "TIER_MIDDLE": "50", "TIER_LOWER": "10"}


class AccountTiersTest(FeatureTest):
    parameter_ts = construct_parameter_timeseries(
        parameter_name_to_value_map={
            "account_tier_names": ACCOUNT_TIER_NAMES,
        },
        default_datetime=DEFAULT_DATETIME,
    )

    def test_get_account_tier_returns_flag_value(self) -> None:

        test_tier = "TIER_MIDDLE"

        mock_vault = self.create_mock(
            parameter_ts=self.parameter_ts,
            flags_ts=construct_flag_timeseries({test_tier: True}, DEFAULT_DATETIME),
        )

        account_tier = account_tiers.get_account_tier(mock_vault)

        self.assertEqual(account_tier, test_tier)

    def test_get_account_tier_returns_last_tier_if_no_flag(self) -> None:

        mock_vault = self.create_mock(parameter_ts=self.parameter_ts)

        account_tier = account_tiers.get_account_tier(mock_vault)

        self.assertEqual(account_tier, loads(ACCOUNT_TIER_NAMES)[-1])

    def test_get_account_tier_returns_previous_tier_active_at_past_datetime(self) -> None:

        mock_vault = self.create_mock(
            parameter_ts=self.parameter_ts,
            flags_ts={
                "TIER_LOWER": FlagTimeseries(
                    [
                        (datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")), True),
                        (datetime(2021, 1, 1, tzinfo=ZoneInfo("UTC")), False),
                    ]
                ),
                "TIER_UPPER": FlagTimeseries(
                    [
                        (datetime(2021, 1, 1, tzinfo=ZoneInfo("UTC")), True),
                    ]
                ),
            },
        )
        account_tier = account_tiers.get_account_tier(
            vault=mock_vault, effective_datetime=datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))
        )

        self.assertEqual(account_tier, "TIER_LOWER")

    def test_get_account_tier_returns_tier_value_at_specified_datetime(self) -> None:

        mock_vault = self.create_mock(
            parameter_ts=self.parameter_ts,
            flags_ts={
                "TIER_LOWER": FlagTimeseries(
                    [
                        (datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")), True),
                        (datetime(2021, 1, 1, tzinfo=ZoneInfo("UTC")), False),
                    ]
                ),
                "TIER_UPPER": FlagTimeseries(
                    [
                        (datetime(2021, 1, 1, tzinfo=ZoneInfo("UTC")), True),
                    ]
                ),
            },
        )
        account_tier = account_tiers.get_account_tier(
            vault=mock_vault, effective_datetime=datetime(2021, 1, 1, tzinfo=ZoneInfo("UTC"))
        )
        self.assertEqual(account_tier, "TIER_UPPER")

    def test_get_account_tier_returns_first_in_tier_name_param_if_multiple_flags_exist(
        self,
    ) -> None:

        mock_vault = self.create_mock(
            parameter_ts=self.parameter_ts,
            flags_ts=construct_flag_timeseries(
                {"TIER_LOWER": True, "TIER_UPPER": True}, DEFAULT_DATETIME
            ),
        )

        account_tier = account_tiers.get_account_tier(mock_vault)

        # returns the first entry in ACCOUNT_TIER_NAMES param that matches a flag
        self.assertEqual(account_tier, "TIER_UPPER")

    def test_get_tiered_parameter_value_based_on_account_tier_convert_function_not_provided(
        self,
    ) -> None:
        test_tier = "TIER_UPPER"
        result = account_tiers.get_tiered_parameter_value_based_on_account_tier(
            tiered_parameter=MIN_BALANCE_THRESHOLD_TIERS, tier=test_tier
        )
        self.assertEqual(result, "100")

    def test_get_tiered_parameter_value_based_on_account_tier_convert_function_provided(
        self,
    ) -> None:
        test_tier = "TIER_LOWER"
        result = account_tiers.get_tiered_parameter_value_based_on_account_tier(
            tiered_parameter=MIN_BALANCE_THRESHOLD_TIERS, tier=test_tier, convert=Decimal
        )
        self.assertEqual(result, Decimal("10"))

    def test_get_tiered_parameter_value_based_on_account_tier_no_value_for_tier(self) -> None:
        test_tier = "RANDOM"
        result = account_tiers.get_tiered_parameter_value_based_on_account_tier(
            tiered_parameter=MIN_BALANCE_THRESHOLD_TIERS, tier=test_tier, convert=Decimal
        )
        self.assertIsNone(result)
