# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from decimal import Decimal
from json import dumps
from unittest.mock import patch, Mock

# common
from inception_sdk.test_framework.contracts.unit.common import (
    ContractFeatureTest,
)
from inception_sdk.vault.contracts.types_extension import (
    Tside,
    UnionItemValue,
)
import library.features.shariah.tiered_profit_calculation as tiered_profit_calculation

DEFAULT_DATE = datetime(2019, 1, 1)

BALANCE_TIER_RANGES = dumps(
    {
        "tier1": {"min": "0"},
        "tier2": {"min": "2000.00"},
        "tier3": {"min": "5000.00"},
    }
)
TIERED_PROFIT_RATES = dumps(
    {
        "MURABAHAH_TIER_UPPER": {
            "tier1": "0.02",
            "tier2": "0.015",
            "tier3": "0.01",
        },
        "MURABAHAH_TIER_MIDDLE": {
            "tier1": "0.0125",
            "tier2": "0.01",
            "tier3": "0.0075",
        },
        "MURABAHAH_TIER_LOWER": {
            "tier1": "0",
            "tier2": "0.0075",
            "tier3": "0.005",
        },
    }
)


class TieredProfitCalculationTest(ContractFeatureTest):
    target_test_file = "library/features/shariah/tiered_profit_calculation.py"
    side = Tside.LIABILITY

    def create_mock(
        self,
        creation_date=DEFAULT_DATE,
        balance_tier_ranges=BALANCE_TIER_RANGES,
        tiered_profit_rates=TIERED_PROFIT_RATES,
        days_in_year=UnionItemValue("365"),
        **kwargs,
    ):

        params = {
            key: {"value": value}
            for key, value in locals().items()
            if key not in self.locals_to_ignore
        }
        parameter_ts = self.param_map_to_timeseries(params, creation_date)
        return super().create_mock(
            parameter_ts=parameter_ts,
            creation_date=creation_date,
            **kwargs,
        )

    @patch("library.features.shariah.tiered_profit_calculation.account_tiers")
    def run_test_scenario(
        self, test_input: dict, expected_output: Decimal, mock_account_tiers: Mock
    ):
        mock_account_tiers.get_account_tier.return_value = "MURABAHAH_TIER_MIDDLE"

        results = tiered_profit_calculation.calculate(**test_input)

        self.assertEqual(results, expected_output)

    def test_calculation_covers_full_tiered_range(self):
        test_input = {
            "vault": self.create_mock(),
            "accrual_capital": Decimal("6392.98"),
            "effective_date": DEFAULT_DATE,
        }

        # tier3 1392.98 * 0.0075/365 ~ 0.02862 rounds down at 5dp
        # tier2 3000 * 0.01/365 ~ 0.08219 rounds down at 5dp
        # tier1 2000 * 0.0125/365 ~ 0.06849 rounds down at 5dp
        self.run_test_scenario(test_input, Decimal("0.17930"))

    def test_calculation_covers_partial_range(self):
        test_input = {
            "vault": self.create_mock(),
            "accrual_capital": Decimal("2388.12"),
            "effective_date": DEFAULT_DATE,
        }

        # tier2 388 * 0.01/365 = 0.01063 rounds down at 5dp
        # tier1 2000 * 0.0125/365 = 0.06849 rounds down at 5dp
        expected_output = Decimal("0.07912")

        self.run_test_scenario(test_input, expected_output)

    def test_calculation_handles_zero_rate(self):
        zero_rate = dumps(
            {
                "MURABAHAH_TIER_MIDDLE": {"tier1": "0", "tier2": "0.01"},
            }
        )
        test_input = {
            "vault": self.create_mock(tiered_profit_rates=zero_rate),
            "accrual_capital": Decimal("2388.12"),
            "effective_date": DEFAULT_DATE,
        }

        # tier2 388 * 0.01/365 ~ 0.01063 rounds down at 5dp
        # tier1 Decimal("2000") * Decimal("0") = 0
        expected_output = Decimal("0.01063")

        self.run_test_scenario(test_input, expected_output)

    def test_calculation_handles_single_balance_tier(self):
        single_balance_tier = dumps(
            {
                "tier1": {"min": "0"},
            }
        )
        test_input = {
            "vault": self.create_mock(balance_tier_ranges=single_balance_tier),
            "accrual_capital": Decimal("2388.12"),
            "effective_date": DEFAULT_DATE,
        }

        # tier1 2388.12 * 0.0125/365 ~ 0.08178 rounds down at 5dp
        expected_output = Decimal("0.08178")

        self.run_test_scenario(test_input, expected_output)

    def test_calculation_defaults_0_rate_if_account_tier_missing(self):
        missing_account_tier = dumps(
            # middle tier missing
            {
                "MURABAHAH_TIER_UPPER": {
                    "tier1": "0.02",
                    "tier2": "0.015",
                    "tier3": "0.01",
                },
            }
        )
        test_input = {
            "vault": self.create_mock(tiered_profit_rates=missing_account_tier),
            "accrual_capital": Decimal("2388.12"),
            "effective_date": DEFAULT_DATE,
        }

        expected_output = Decimal("0.00000")

        self.run_test_scenario(test_input, expected_output)

    def test_calculation_defaults_0_rate_if_balance_tier_missing(self):
        missing_account_tier = dumps(
            {
                "MURABAHAH_TIER_MIDDLE": {
                    # tier 1 missing
                    "tier2": "0.015",
                },
            }
        )
        test_input = {
            "vault": self.create_mock(tiered_profit_rates=missing_account_tier),
            "accrual_capital": Decimal("2388.12"),
            "effective_date": DEFAULT_DATE,
        }

        # tier2 388.12 * 0.015/365 ~ 0.01595 rounds down at 5dp
        # tier1 2000 * 0 = 0
        expected_output = Decimal("0.01595")

        self.run_test_scenario(test_input, expected_output)

    def test_calculation_accrues_0_on_unconfigured_balance_range(self):
        unconfigured_0_to_500 = dumps(
            {
                "tier1": {"min": "500"},
                "tier2": {"min": "2000.00"},
                "tier3": {"min": "5000.00"},
            }
        )
        test_input = {
            "vault": self.create_mock(balance_tier_ranges=unconfigured_0_to_500),
            "accrual_capital": Decimal("2388.12"),
            "effective_date": DEFAULT_DATE,
        }

        # tier2 377.12 * 0.01/365 ~ 0.01063 rounds down at 5dp
        # tier1 1500 * 0.0125/365 ~ 0.05136 rounds down at 5dp
        # unconfigured balance range 500 * 0 = 0
        expected_output = Decimal("0.06199")
        self.run_test_scenario(test_input, expected_output)

    def test_calculation_handles_single_balance_tier_360_days(self):
        single_balance_tier = dumps(
            {
                "tier1": {"min": "0"},
            }
        )
        test_input = {
            "vault": self.create_mock(
                balance_tier_ranges=single_balance_tier,
                days_in_year=UnionItemValue("360"),
            ),
            "accrual_capital": Decimal("2388.12"),
            "effective_date": DEFAULT_DATE,
        }

        # tier1 2388.12 * 0.0125/360 ~ 0.08292 rounds down at 5dp
        expected_output = Decimal("0.08292")

        self.run_test_scenario(test_input, expected_output)

    def test_calculation_handles_single_balance_tier_366_days(self):
        single_balance_tier = dumps(
            {
                "tier1": {"min": "0"},
            }
        )
        test_input = {
            "vault": self.create_mock(
                balance_tier_ranges=single_balance_tier,
                days_in_year=UnionItemValue("366"),
            ),
            "accrual_capital": Decimal("2388.12"),
            "effective_date": DEFAULT_DATE,
        }

        # tier1 2388.12 * 0.0125/366 ~ 0.08156 rounds down at 5dp
        expected_output = Decimal("0.08156")

        self.run_test_scenario(test_input, expected_output)
