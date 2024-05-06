# standard libs
from datetime import datetime
from decimal import Decimal
from typing import Optional

# features
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.lending.interest_rate.fixed as fixed_rate
import library.features.v4.lending.interest_rate.variable as variable_rate
import library.features.v4.lending.lending_interfaces as lending_interfaces
import library.features.v4.lending.term_helpers as term_helpers

# contracts api
from contracts_api import (
    BalanceDefaultDict,
    NumberShape,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    StringShape,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

PARAM_FIXED_INTEREST_TERM = "fixed_interest_term"
PARAM_IS_FIXED_INTEREST = "is_fixed_interest"
is_fixed_interest_param = Parameter(
    name=PARAM_IS_FIXED_INTEREST,
    shape=StringShape(),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Is this account within the fixed interest period.",
    display_name="In Fixed Interest Period",
)
fixed_interest_term_param = Parameter(
    name=PARAM_FIXED_INTEREST_TERM,
    shape=NumberShape(min_value=Decimal(0), step=Decimal(1)),
    level=ParameterLevel.INSTANCE,
    description="The agreed length of the fixed rate portion (in months).",
    display_name="Fixed Rate Term (months)",
    default_value=Decimal(0),
    update_permission=ParameterUpdatePermission.OPS_EDITABLE,
)
parameters = [
    is_fixed_interest_param,
    fixed_interest_term_param,
]


def is_within_fixed_rate_term(
    vault: SmartContractVault,
    effective_datetime: datetime,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> bool:
    fixed_rate_term = int(utils.get_parameter(vault, "fixed_interest_term"))
    if fixed_rate_term == 0:
        return False

    # this allows us to avoid fetching balances in activation hook
    if effective_datetime == vault.get_account_creation_datetime():
        elapsed_term = 0
    else:
        if balances is None:
            balances = vault.get_balances_observation(
                fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
            ).balances
        if denomination is None:
            denomination = utils.get_parameter(vault=vault, name="denomination")

        elapsed_term = term_helpers.calculate_elapsed_term(
            balances=balances, denomination=denomination
        )

    return elapsed_term < fixed_rate_term


def get_daily_interest_rate(
    vault: SmartContractVault,
    effective_datetime: datetime,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    is_fixed_interest = is_within_fixed_rate_term(
        vault=vault,
        effective_datetime=effective_datetime,
        balances=balances,
        denomination=denomination,
    )
    if is_fixed_interest:
        return fixed_rate.get_daily_interest_rate(
            vault=vault, effective_datetime=effective_datetime
        )
    else:
        return variable_rate.get_daily_interest_rate(
            vault=vault, effective_datetime=effective_datetime
        )


def get_monthly_interest_rate(
    vault: SmartContractVault,
    effective_datetime: datetime,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    is_fixed_interest = is_within_fixed_rate_term(
        vault=vault,
        effective_datetime=effective_datetime,
        balances=balances,
        denomination=denomination,
    )
    if is_fixed_interest:
        return fixed_rate.get_monthly_interest_rate(
            vault=vault, effective_datetime=effective_datetime
        )
    else:
        return variable_rate.get_monthly_interest_rate(
            vault=vault, effective_datetime=effective_datetime
        )


def get_annual_interest_rate(
    vault: SmartContractVault,
    effective_datetime: datetime,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    is_fixed_interest = is_within_fixed_rate_term(
        vault=vault,
        effective_datetime=effective_datetime,
        balances=balances,
        denomination=denomination,
    )
    if is_fixed_interest:
        return fixed_rate.get_annual_interest_rate(
            vault=vault, effective_datetime=effective_datetime
        )
    else:
        return variable_rate.get_annual_interest_rate(
            vault=vault, effective_datetime=effective_datetime
        )


def should_trigger_reamortisation(
    vault: SmartContractVault,
    period_start_datetime: datetime,
    period_end_datetime: datetime,
    elapsed_term: int,
) -> bool:
    """
    Determines if re-amortisation is required by checking if we have changed interest rates between
    the period start and end. This can be because:
    - rate type is variable and rate has changed
    - rate type has gone from fixed to variable and the fixed rate and variable rate differ

    :param vault: Vault object used to fetch balances/parameters
    :param period_start_datetime: datetime of the period start, typically this will be the datetime
    of the previous due amount calculation. This is intentionally not an Optional[] argument since
    period_start_datetime=None would result in comparing the monthly interest rate between latest()
    and period_end_datetime.
    :param period_end_datetime: datetime of the period end, typically the effective_datetime of the
    current due amount calculation event
    :param elapsed_term: the number of months that have elapsed as of the period_end_datetime
    :return: True if re-amortisation is needed, False otherwise
    """

    if is_within_fixed_rate_term(vault=vault, effective_datetime=period_end_datetime):
        return False
    # we would ideally use is_within_fixed_rate_term as of period_start_datetime and
    # period_end_datetime, but this would require having balances as of period_start_datetime
    # and we can't define this in ODF syntax
    # the elapsed term will only equal fixed interest term when we go from fixed to variable
    elif elapsed_term == int(utils.get_parameter(vault, "fixed_interest_term")):
        return variable_rate.get_annual_interest_rate(
            vault=vault, effective_datetime=period_end_datetime
        ) != fixed_rate.get_annual_interest_rate(
            vault=vault, effective_datetime=period_end_datetime
        )
    else:
        return variable_rate.should_trigger_reamortisation(
            vault, period_start_datetime, period_end_datetime, elapsed_term
        )


InterestRate = lending_interfaces.InterestRate(
    get_daily_interest_rate=get_daily_interest_rate,
    get_monthly_interest_rate=get_monthly_interest_rate,
    get_annual_interest_rate=get_annual_interest_rate,
)

ReamortisationCondition = lending_interfaces.ReamortisationCondition(
    should_trigger_reamortisation=should_trigger_reamortisation
)
