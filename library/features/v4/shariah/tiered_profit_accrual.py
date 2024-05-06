# standard libs
from datetime import datetime
from decimal import Decimal
from json import dumps
from typing import Optional

# features
import library.features.v4.common.accruals as accruals
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.shariah.shariah_interfaces as shariah_interfaces

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    AccountIdShape,
    BalanceDefaultDict,
    CustomInstruction,
    NumberShape,
    Parameter,
    ParameterLevel,
    ScheduledEvent,
    SmartContractEventType,
    StringShape,
    UnionItem,
    UnionItemValue,
    UnionShape,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# Constants
ACCRUAL_EVENT = "ACCRUE_PROFIT"
ACCRUED_PROFIT_PAYABLE = "ACCRUED_PROFIT_PAYABLE"

PROFIT_ACCRUAL_PREFIX = "profit_accrual"
PARAM_ACCRUAL_PRECISION = "accrual_precision"
PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT = "accrued_profit_payable_account"
PARAM_DAYS_IN_YEAR = "days_in_year"
PARAM_PROFIT_ACCRUAL_HOUR = f"{PROFIT_ACCRUAL_PREFIX}_hour"
PARAM_PROFIT_ACCRUAL_MINUTE = f"{PROFIT_ACCRUAL_PREFIX}_minute"
PARAM_PROFIT_ACCRUAL_SECOND = f"{PROFIT_ACCRUAL_PREFIX}_second"
PARAM_TIERED_PROFIT_RATES = "tiered_profit_rates"

# Fetchers
data_fetchers = [fetchers.EOD_FETCHER]

# Parameters
days_in_year_parameter = Parameter(
    name=PARAM_DAYS_IN_YEAR,
    shape=UnionShape(
        items=[
            UnionItem(key="actual", display_name="Actual"),
            UnionItem(key="366", display_name="366"),
            UnionItem(key="365", display_name="365"),
            UnionItem(key="360", display_name="360"),
        ]
    ),
    level=ParameterLevel.TEMPLATE,
    description="The days in the year for profit accrual calculation."
    ' Valid values are "actual", "366", "365", "360"',
    display_name="Profit Accrual Days In Year",
    default_value=UnionItemValue(key="365"),
)

accrual_precision_parameter = Parameter(
    name=PARAM_ACCRUAL_PRECISION,
    level=ParameterLevel.TEMPLATE,
    description="Precision needed for profit accruals.",
    display_name="Profit Accrual Precision",
    shape=NumberShape(min_value=0, max_value=15, step=1),
    default_value=Decimal(5),
)

schedule_parameters = [
    Parameter(
        name=PARAM_PROFIT_ACCRUAL_HOUR,
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which profit is accrued.",
        display_name="Profit Accrual Hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_PROFIT_ACCRUAL_MINUTE,
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which profit is accrued.",
        display_name="Profit Accrual Minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_PROFIT_ACCRUAL_SECOND,
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which profit is accrued.",
        display_name="Profit Accrual Second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
]

tiered_parameter = Parameter(
    name=PARAM_TIERED_PROFIT_RATES,
    shape=StringShape(),
    level=ParameterLevel.TEMPLATE,
    display_name="Tiered Gross Profit Rate",
    description="Tiered profit rates applicable to the main denomination as determined by "
    "both the account tier and gross balance. The account tier is determined by flags and "
    "is mapped to a dictionary of gross balance to profit rate",
    default_value=dumps(
        {
            "STANDARD": {
                "0.00": "0.01",
                "1000.00": "0.02",
                "3000.00": "0.035",
                "7500.00": "0.05",
                "10000.00": "0.06",
            },
        }
    ),
)

accrued_profit_payable_account_parameter = Parameter(
    name=PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT,
    level=ParameterLevel.TEMPLATE,
    description="Internal account for accrued profit payable balance.",
    display_name="Accrued Profit Payable Account",
    shape=AccountIdShape(),
    default_value=ACCRUED_PROFIT_PAYABLE,
)

all_parameters = [
    accrual_precision_parameter,
    accrued_profit_payable_account_parameter,
    days_in_year_parameter,
    tiered_parameter,
    *schedule_parameters,
]


def event_types(product_name: str) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
            name=ACCRUAL_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{ACCRUAL_EVENT}_AST"],
        )
    ]


def scheduled_events(
    vault: SmartContractVault, start_datetime: datetime
) -> dict[str, ScheduledEvent]:
    return {
        ACCRUAL_EVENT: utils.daily_scheduled_event(
            vault=vault, start_datetime=start_datetime, parameter_prefix=PROFIT_ACCRUAL_PREFIX
        )
    }


def accrue_profit(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    account_tier: str,
    accrual_address: str = ACCRUED_PROFIT_PAYABLE,
    account_type: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Creates the posting instructions to accrue profit on the balances specified by
    the denomination and capital addresses parameters
    :param vault: the vault object to use to for retrieving data and instructing directives
    :param effective_datetime: the effective date to retrieve capital balances to accrue on
    :param accrual_address: balance address for the accrual amount to be assigned
    :return: the accrual posting custom instructions
    """
    denomination = utils.get_parameter(vault, name="denomination")
    accrued_profit_payable_account: str = utils.get_parameter(
        vault, name=PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT
    )
    days_in_year: str = utils.get_parameter(vault, name=PARAM_DAYS_IN_YEAR, is_union=True)
    rounding_precision: int = utils.get_parameter(vault, name=PARAM_ACCRUAL_PRECISION)
    # these rates are tiered by account tier _and_ balance tier
    tiered_rates: dict[str, str] = utils.get_parameter(
        vault,
        name=PARAM_TIERED_PROFIT_RATES,
        at_datetime=effective_datetime,
        is_json=True,
    ).get(account_tier, {})

    if not tiered_rates:
        return []

    amount_to_accrue, instruction_detail = get_tiered_accrual_amount(
        effective_balance=get_accrual_capital(vault),
        effective_datetime=effective_datetime,
        tiered_profit_rates=tiered_rates,
        days_in_year=days_in_year,
        precision=rounding_precision,
    )

    if account_type is None:
        account_type = ""

    instruction_details = utils.standard_instruction_details(
        description=instruction_detail.strip(),
        event_type=f"{ACCRUAL_EVENT}",
        account_type=account_type,
    )

    # Negative profit accrual is not supported
    if amount_to_accrue > 0:
        return accruals.accrual_custom_instruction(
            customer_account=vault.account_id,
            customer_address=accrual_address,
            denomination=denomination,
            amount=amount_to_accrue,
            internal_account=accrued_profit_payable_account,
            payable=True,
            instruction_details=instruction_details,
        )
    else:
        return []


def get_tiered_accrual_amount(
    *,
    effective_balance: Decimal,
    effective_datetime: datetime,
    tiered_profit_rates: dict[str, str],
    days_in_year: str,
    precision: int = 5,
) -> tuple[Decimal, str]:
    """
    Calculate the amount to accrue on each balance portion by tier rate (to defined precision).
    Provide instruction details highlighting the breakdown of the tiered accrual.
    :param effective_balance: balance to accrue on
    :param effective_datetime: the date to accrue as-of. This will affect the conversion of yearly
    to daily rates if `days_in_year` is set to `actual`
    :param tiered_profit_rates: tiered profit rates parameter
    :param days_in_year: days in year parameter
    :param accrual_precision: accrual precision parameter
    :return: rounded accrual_amount and instruction_details
    """
    daily_accrual_amount = Decimal("0")
    instruction_detail = ""

    tiered_profit_rates = dict(sorted(tiered_profit_rates.items(), key=lambda x: x[1]))
    for index, (tier_min, tier_rate) in enumerate(tiered_profit_rates.items()):
        rate = Decimal(tier_rate)
        # Tier max is next tier 'min value' if exists
        tier_max = determine_tier_max(list(tiered_profit_rates.keys()), index)

        tier_balances = determine_tier_balance(
            effective_balance=effective_balance, tier_min=Decimal(tier_min), tier_max=tier_max
        )
        if tier_balances != Decimal(0):
            daily_rate = utils.yearly_to_daily_rate(
                effective_date=effective_datetime,
                yearly_rate=rate,
                days_in_year=days_in_year,
            )

            daily_accrual_amount += tier_balances * daily_rate
            instruction_detail = (
                f"{instruction_detail}Accrual on {tier_balances:.2f} "
                f"at annual rate of {rate*100:.2f}%. "
            )

    return (
        utils.round_decimal(amount=daily_accrual_amount, decimal_places=precision),
        instruction_detail,
    )


def determine_tier_max(tier_range_list: list[str], index: int) -> Optional[Decimal]:
    return Decimal(tier_range_list[index + 1]) if (index + 1) < len(tier_range_list) else None


def determine_tier_balance(
    effective_balance: Decimal,
    tier_min: Optional[Decimal] = None,
    tier_max: Optional[Decimal] = None,
) -> Decimal:
    """
    Determines a tier's balance based on min and max. Min and max must be of same sign or
    zero is returned (use Decimal("-0") if required). If neither are provided, zero is returned
    :param tier_min: the minimum balance included in the tier. Any amount below is excluded.
    Defaults to 0 if tier_max is +ve or unbounded if tier_max is -ve
    :param tier_max: the maximum balance included in the tier, exclusive. Any amount greater is
    excluded. Defaults to Decimal("-0") if tier_min is -ve or unbounded if tier_min is +ve
    :param effective_balance: the balance to check against the tier min/max
    :return: the portion of the effective balance that is included in the tier
    """
    # Could be expressed more simply, but this provides clearer coverage and type checks
    if tier_min is None:
        if tier_max is None:
            return Decimal("0")
        if tier_max.is_signed():
            tier_min = effective_balance
        else:
            tier_min = Decimal("0")
    if tier_max is None:
        if tier_min.is_signed():
            tier_max = Decimal("-0")
        else:
            tier_max = effective_balance

    # we don't handle ranges where min and max have different signs
    # is_signed() detects negative 0 whereas < 0 comparison does not
    if tier_max.is_signed() ^ tier_min.is_signed():
        return Decimal("0")

    if tier_max.is_signed():
        # Next statement could go positive otherwise
        if tier_min >= tier_max:
            return Decimal("0")

        return max(effective_balance, tier_min) - max(effective_balance, tier_max)
    else:
        # Next statement could go negative otherwise
        if tier_max <= tier_min:
            return Decimal("0")

        return min(effective_balance, tier_max) - min(effective_balance, tier_min)


def get_accrual_capital(
    vault: SmartContractVault,
    *,
    capital_addresses: Optional[list[str]] = None,
) -> Decimal:
    """
    Calculates the sum of balances that will be used to accrue profit on.
    We should check the last possible time capital could accrue
    (i.e. at 23:59:59.999999 on the day before effective_datetime)
    :param vault: the vault object to use to for retrieving data and instructing directives
    :param capital_addresses: list of balance addresses that will be summed up to provide
    the amount to accrue profit on. Defaults to the DEFAULT_ADDRESS
    :return: the sum of balances on which profit will be accrued on
    """
    denomination = utils.get_parameter(vault, name="denomination")
    balances = vault.get_balances_observation(fetcher_id=fetchers.EOD_FETCHER_ID).balances

    accrual_balance = utils.sum_balances(
        balances=balances,
        addresses=capital_addresses or [DEFAULT_ADDRESS],
        denomination=denomination,
    )

    # This is only used for deposit accruals, so we do not want to accrue on negative balances.
    return accrual_balance if accrual_balance > 0 else Decimal(0)


def get_daily_profit_rate(
    *, annual_rate: str, days_in_year: str, effective_datetime: datetime
) -> Decimal:
    return utils.yearly_to_daily_rate(
        effective_date=effective_datetime,
        yearly_rate=Decimal(annual_rate),
        days_in_year=days_in_year,
    )


def get_accrued_profit(
    *,
    balances: BalanceDefaultDict,
    denomination: str,
    accrued_profit_address: str = ACCRUED_PROFIT_PAYABLE,
) -> Decimal:
    """
    Retrieves the existing balance for accrued profit at a specific time
    :param balances: the balances to sum accrued profit
    :param denomination: the denomination of the capital balances and the profit accruals
    :param accrued_profit_address: the address name in which we are storing the accrued profit
    :return: the value of the balance at the requested time
    """
    return utils.balance_at_coordinates(
        balances=balances, address=accrued_profit_address, denomination=denomination
    )


def get_profit_reversal_postings(
    *,
    vault: SmartContractVault,
    accrued_profit_address: str = ACCRUED_PROFIT_PAYABLE,
    event_name: str,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    account_type: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Reverse any accrued profit and apply back to the internal account.
    During account closure, any positively accrued profit that has not been applied
    should return back to the bank's internal account.
    :param vault: the vault object used to create profit reversal postings
    :param accrued_profit_address: the balance address used to store the accrued profit
    :param event_name: the name of the event reversing any accrue profit
    :param balances: balances to use to get profit to reverse. Defaults to previous EOD balances
    if not, relative to hook execution effective datetime
    :param denomination: the denomination of the profit accruals to reverse
    :param account_type: the account type to be populated on posting instruction details
    :return: the accrued profit reversal posting instructions
    """
    accrued_profit_payable_account: str = utils.get_parameter(
        vault, name=PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT
    )
    if denomination is None:
        denomination = str(utils.get_parameter(vault, name="denomination"))
    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers.EOD_FETCHER_ID).balances

    accrued_profit = get_accrued_profit(
        balances=balances,
        denomination=denomination,
        accrued_profit_address=accrued_profit_address,
    )

    instruction_details = utils.standard_instruction_details(
        description=f"Reversal of accrued profit of value {accrued_profit} {denomination}"
        " due to account closure.",
        event_type=f"{event_name}",
        gl_impacted=True,
        account_type=account_type or "",
    )

    # negative profit accruals are not supported
    if accrued_profit > 0:
        return accruals.accrual_custom_instruction(
            customer_account=vault.account_id,
            customer_address=accrued_profit_address,
            denomination=denomination,
            amount=accrued_profit,
            internal_account=accrued_profit_payable_account,
            payable=True,
            instruction_details=instruction_details,
            reversal=True,
        )
    else:
        return []


feature = shariah_interfaces.ProfitAccrual(
    get_accrual_amount=get_tiered_accrual_amount,
)
