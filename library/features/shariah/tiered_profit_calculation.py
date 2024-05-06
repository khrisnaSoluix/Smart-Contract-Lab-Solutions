from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from json import dumps as json_dumps
from typing import NamedTuple, Callable

# inception lib
from inception_sdk.vault.contracts.types_extension import (
    Level,
    Parameter,
    StringShape,
    UnionShape,
    UnionItem,
    UnionItemValue,
    Vault,
)
import library.features.common.utils as utils
import library.features.common.account_tiers as account_tiers


parameters = [
    Parameter(
        name="balance_tier_ranges",
        level=Level.TEMPLATE,
        description="Deposit balance ranges used to determine applicable profit rate."
        "minimum in range is exclusive and maximum is inclusive",
        display_name="Balance tiers",
        shape=StringShape,
        default_value=json_dumps(
            {
                "tier1": {"min": "0"},
                "tier2": {"min": "10000.00"},
                "tier3": {"min": "25000.00"},
                "tier4": {"min": "50000.00"},
                "tier5": {"min": "100000.00"},
            }
        ),
    ),
    Parameter(
        name="tiered_profit_rates",
        level=Level.TEMPLATE,
        description="Tiered profit rates applicable to the main denomination as determined by the"
        " both balance tier ranges and account tiers. "
        "This is the gross profit rate (per annum) used to calculate profit on "
        "customers deposits. "
        "This is accrued daily and applied according to the schedule.",
        display_name="Tiered profit rates (p.a.)",
        shape=StringShape,
        default_value=json_dumps(
            {
                "STANDARD": {
                    "tier1": "0.0025",
                    "tier2": "0.0075",
                    "tier3": "0.015",
                    "tier4": "0.02",
                    "tier5": "0.025",
                },
            }
        ),
    ),
    Parameter(
        name="days_in_year",
        level=Level.TEMPLATE,
        description="The days in the year for profit accrual calculation."
        ' Valid values are "actual", "365", "366", "360".'
        ' Any invalid values will default to "actual".',
        display_name="Profit accrual days in year",
        shape=UnionShape(
            UnionItem(key="actual", display_name="Actual"),
            UnionItem(key="365", display_name="365"),
            UnionItem(key="366", display_name="366"),
            UnionItem(key="360", display_name="360"),
        ),
        default_value=UnionItemValue(key="actual"),
    ),
]


def calculate(vault: Vault, accrual_capital: Decimal, effective_date: datetime):
    amount_to_accrue = Decimal("0")
    account_tier = account_tiers.get_account_tier(vault)
    balance_tier_ranges = utils.get_parameter(vault, "balance_tier_ranges", is_json=True)
    tiered_profit_rates = utils.get_parameter(vault, "tiered_profit_rates", is_json=True).get(
        account_tier, {}
    )

    days_in_year = utils.get_parameter(vault, "days_in_year", union=True)

    for tier_name, tier_range in reversed(balance_tier_ranges.items()):

        tier_min = Decimal(tier_range.get("min"))

        if accrual_capital > tier_min:
            effective_balance = accrual_capital - tier_min

            # if tier name not configured, defaults to rate of 0
            profit_rate = Decimal(tiered_profit_rates.get(tier_name, "0"))
            daily_rate = utils.yearly_to_daily_rate(
                profit_rate, effective_date.year, days_in_year=days_in_year
            )
            amount_to_accrue += utils.round_decimal(
                abs(effective_balance * daily_rate), decimal_places=5, rounding=ROUND_DOWN
            )
            accrual_capital -= effective_balance
    return amount_to_accrue


TieredProfitCalculation = NamedTuple(
    "TieredProfitCalculation",
    [
        ("parameters", list),
        ("calculate", Callable),
    ],
)

feature = TieredProfitCalculation(
    parameters=parameters,
    calculate=calculate,
)
