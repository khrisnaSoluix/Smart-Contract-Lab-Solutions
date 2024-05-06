# CBF: Scheduled Deposit Interest Accrual
# CBF: Client Triggered Deposit Interest Application
# Note: The functionality to decide between capitalize and revert the accrued interest described
# In the CBF has not been implemented yet. Currently only the revert option has been implemented
# And is part of the Tiered Interest Accrual feature.

# standard libs
from datetime import datetime
from decimal import Decimal
from json import dumps
from typing import Optional

# features
import library.features.v4.common.accruals as accruals
import library.features.common.common_parameters as common_parameters
import library.features.v4.common.interest_accrual_common as interest_accrual_common
import library.features.v4.common.utils as utils
import library.features.v4.deposit.interest.deposit_interest_accrual_common as deposit_interest_accrual_common  # noqa: E501

# contracts api
from contracts_api import CustomInstruction, Parameter, ParameterLevel, StringShape

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# Events
ACCRUAL_EVENT = interest_accrual_common.ACCRUAL_EVENT

# Balance Addresses
ACCRUED_INTEREST_PAYABLE = interest_accrual_common.ACCRUED_INTEREST_PAYABLE
ACCRUED_INTEREST_RECEIVABLE = interest_accrual_common.ACCRUED_INTEREST_RECEIVABLE

# Parameters
PARAM_DAYS_IN_YEAR = interest_accrual_common.PARAM_DAYS_IN_YEAR
PARAM_ACCRUAL_PRECISION = interest_accrual_common.PARAM_ACCRUAL_PRECISION
INTEREST_ACCRUAL_PREFIX = interest_accrual_common.INTEREST_ACCRUAL_PREFIX
PARAM_INTEREST_ACCRUAL_HOUR = interest_accrual_common.PARAM_INTEREST_ACCRUAL_HOUR
PARAM_INTEREST_ACCRUAL_MINUTE = interest_accrual_common.PARAM_INTEREST_ACCRUAL_MINUTE
PARAM_INTEREST_ACCRUAL_SECOND = interest_accrual_common.PARAM_INTEREST_ACCRUAL_SECOND
PARAM_ACCRUED_INTEREST_PAYABLE_ACCOUNT = (
    interest_accrual_common.PARAM_ACCRUED_INTEREST_PAYABLE_ACCOUNT
)
PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = (
    interest_accrual_common.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
)

PARAM_TIERED_INTEREST_RATES = "tiered_interest_rates"
tiered_interest_rates_parameter = Parameter(
    name=PARAM_TIERED_INTEREST_RATES,
    shape=StringShape(),
    level=ParameterLevel.TEMPLATE,
    description="Map Of Minimum Balance To Gross Interest Rate For Positive Balances.",
    display_name="Tiered Gross Interest Rate",
    default_value=dumps(
        {
            "0.00": "0.01",
            "1000.00": "0.02",
            "3000.00": "0.035",
            "7500.00": "0.05",
            "10000.00": "0.06",
        },
    ),
)

parameters = [
    tiered_interest_rates_parameter,
    interest_accrual_common.accrued_interest_payable_account_param,
    interest_accrual_common.accrued_interest_receivable_account_param,
    *interest_accrual_common.accrual_parameters,
    *interest_accrual_common.schedule_parameters,
]

# Functions
event_types = interest_accrual_common.event_types
scheduled_events = interest_accrual_common.scheduled_events
get_accrual_capital = deposit_interest_accrual_common.get_accrual_capital
get_interest_reversal_postings = deposit_interest_accrual_common.get_interest_reversal_postings


# Parameter Getters
def get_tiered_interest_rates_parameter(
    *,
    vault: SmartContractVault,
    effective_datetime: Optional[datetime] = None,
) -> dict[str, str]:
    return utils.get_parameter(
        vault=vault,
        name=PARAM_TIERED_INTEREST_RATES,
        at_datetime=effective_datetime,
        is_json=True,
    )


# Interest calculations
def accrue_interest(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
) -> list[CustomInstruction]:
    """
    Creates the posting instructions to accrue interest on the balances specified by
    the denomination and capital addresses parameters
    :param vault: the vault object to use to for retrieving data and instructing directives
    :param effective_datetime: the effective date to retrieve capital balances to accrue on
    :return: the accrual posting custom instructions
    """
    denomination = common_parameters.get_denomination_parameter(vault=vault)
    accrued_interest_payable_account = (
        interest_accrual_common.get_accrued_interest_payable_account_parameter(vault=vault)
    )
    accrued_interest_receivable_account = (
        interest_accrual_common.get_accrued_interest_receivable_account_parameter(vault=vault)
    )
    days_in_year = interest_accrual_common.get_days_in_year_parameter(vault=vault)
    rounding_precision = interest_accrual_common.get_accrual_precision_parameter(vault=vault)
    tiered_rates = get_tiered_interest_rates_parameter(vault=vault)

    accrual_amount, instruction_detail = get_tiered_accrual_amount(
        effective_balance=get_accrual_capital(vault),
        effective_datetime=effective_datetime,
        tiered_interest_rates=tiered_rates,
        days_in_year=days_in_year,
        precision=rounding_precision,
    )

    instruction_details = {"description": instruction_detail.strip(), "event": ACCRUAL_EVENT}

    target_customer_address, target_internal_account = (
        (ACCRUED_INTEREST_PAYABLE, accrued_interest_payable_account)
        if accrual_amount >= 0
        else (ACCRUED_INTEREST_RECEIVABLE, accrued_interest_receivable_account)
    )

    return accruals.accrual_custom_instruction(
        customer_account=vault.account_id,
        customer_address=target_customer_address,
        denomination=denomination,
        amount=abs(accrual_amount),
        internal_account=target_internal_account,
        payable=accrual_amount >= 0,
        instruction_details=instruction_details,
    )


def get_tiered_accrual_amount(
    *,
    effective_balance: Decimal,
    effective_datetime: datetime,
    tiered_interest_rates: dict[str, str],
    days_in_year: str,
    precision: int = 5,
) -> tuple[Decimal, str]:
    """
    Calculate the amount to accrue on each balance portion by tier rate (to defined precision).
    Provide instruction details highlighting the breakdown of the tiered accrual.
    :param effective_balance: balance to accrue on
    :param effective_datetime: the date to accrue as-of. This will affect the conversion of yearly
    to daily rates if `days_in_year` is set to `actual`
    :param tiered_interest_rates: tiered interest rates parameter
    :param days_in_year: days in year parameter
    :param accrual_precision: accrual precision parameter
    :return: rounded accrual_amount and instruction_details
    """
    daily_accrual_amount = Decimal("0")
    instruction_detail = ""

    tiered_interest_rates = dict(sorted(tiered_interest_rates.items(), key=lambda x: x[1]))
    for index, (tier_min, tier_rate) in enumerate(tiered_interest_rates.items()):
        rate = Decimal(tier_rate)
        # Tier max is next tier 'min value' if exists
        tier_max = determine_tier_max(list(tiered_interest_rates.keys()), index)

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
    :param tier_min: the minimum balance in the tier, exclusive. Any amount at or below is excluded.
    Defaults to 0 if tier_max is +ve, unbounded is tier_max is -ve
    :param tier_max: the maximum balance included in the tier, inclusive. Any amount greater is
    excluded. Defaults to Decimal("-0") if tier_min is -ve,  unbounded if tier_min is +ve
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
