# CBF: Fixed Deposit Interest Accrual

# standard libs
from datetime import datetime
from decimal import Decimal
from typing import Optional

# features
import library.features.v4.common.accruals as accruals
import library.features.common.common_parameters as common_parameters
import library.features.v4.common.interest_accrual_common as interest_accrual_common
import library.features.v4.common.utils as utils
import library.features.v4.deposit.interest.deposit_interest_accrual_common as deposit_interest_accrual_common  # noqa: E501

# contracts api
from contracts_api import (
    BalanceDefaultDict,
    CustomInstruction,
    NumberShape,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
)

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

# Parameters
PARAM_FIXED_INTEREST_RATE = "fixed_interest_rate"

"""
This feature provides two parameter definitions for the `fixed_interest_rate` parameter
- fixed_interest_parameter support positive and negative interest rates
- positive_fixed_interest_parameter support positive only interest rates

When using this feature in a product, the template can include only one of
- `fixed_interest_parameters`
- `positive_fixed_interest_parameters`
in the parameters metadata. The logic will work with either of these parameter lists included.

Please refer to `documentation/design_decisions/cbf_design_docs/fixed_deposit_interest_accrual.md`
for more information.
"""
fixed_interest_parameter = Parameter(
    name=PARAM_FIXED_INTEREST_RATE,
    level=ParameterLevel.INSTANCE,
    description="The fixed annual rate of the product",
    display_name="Fixed Interest Rate",
    shape=NumberShape(),
    default_value=Decimal("0.00"),
    update_permission=ParameterUpdatePermission.OPS_EDITABLE,
)
fixed_interest_parameters = [
    fixed_interest_parameter,
    interest_accrual_common.accrued_interest_payable_account_param,
    interest_accrual_common.accrued_interest_receivable_account_param,
    *interest_accrual_common.accrual_parameters,
    *interest_accrual_common.schedule_parameters,
]

positive_fixed_interest_parameter = Parameter(
    name=PARAM_FIXED_INTEREST_RATE,
    level=ParameterLevel.INSTANCE,
    description="The fixed annual rate of the product",
    display_name="Fixed Interest Rate",
    shape=NumberShape(min_value=Decimal("0")),
    default_value=Decimal("0.00"),
    update_permission=ParameterUpdatePermission.OPS_EDITABLE,
)
positive_fixed_interest_parameters = [
    positive_fixed_interest_parameter,
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
def get_fixed_interest_rate_parameter(
    *,
    vault: SmartContractVault,
    effective_datetime: Optional[datetime] = None,
) -> Decimal:
    return Decimal(
        utils.get_parameter(
            vault=vault, name=PARAM_FIXED_INTEREST_RATE, at_datetime=effective_datetime
        )
    )


def get_daily_interest_rate(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
) -> Decimal:
    annual_rate = get_fixed_interest_rate_parameter(vault=vault)
    days_in_year = interest_accrual_common.get_days_in_year_parameter(vault=vault)
    return utils.yearly_to_daily_rate(
        effective_date=effective_datetime, yearly_rate=annual_rate, days_in_year=days_in_year
    )


# Interest calculations
def accrue_interest(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    account_type: str,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
    accrued_interest_payable_account: Optional[str] = None,
    accrued_interest_receivable_account: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Accrue interest on the sum of EOD balances held at the capital addresses.

    :param vault: the vault object to use to for retrieving data and instructing directives
    :param effective_datetime: the effective date to retrieve capital balances to accrue on
    :param account_type: the account type for GL purposes (e.g. to identify postings pertaining to
    current accounts vs savings accounts)
    :param denomination: the denomination of the account
    :param balances: balances to accrue interest on. EOD balances are fetched if not provided
    :param accrued_interest_payable_account: the accrued interest payable account, defaults
    to the value in the parameter if not provided
    :param accrued_interest_receivable_account: the accrued interest receivable account, defaults
    to the value in the parameter if not provided
    :return: the accrual posting custom instructions
    """
    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)
    rounding_precision = interest_accrual_common.get_accrual_precision_parameter(vault=vault)

    daily_rate = get_daily_interest_rate(vault=vault, effective_datetime=effective_datetime)
    effective_balance = get_accrual_capital(vault=vault, balances=balances)

    accrual_amount = utils.round_decimal(
        amount=effective_balance * daily_rate,
        decimal_places=rounding_precision,
    )

    instruction_details = utils.standard_instruction_details(
        description=f"Daily interest accrued at {(daily_rate * 100):0.5f}%"
        f" on balance of {effective_balance:0.2f}",
        event_type=interest_accrual_common.ACCRUAL_EVENT,
        gl_impacted=True,
        account_type=account_type,
    )

    (
        target_customer_address,
        target_internal_account,
    ) = deposit_interest_accrual_common.get_target_customer_address_and_internal_account(
        vault=vault,
        accrual_amount=accrual_amount,
        accrued_interest_payable_account=accrued_interest_payable_account,
        accrued_interest_receivable_account=accrued_interest_receivable_account,
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


get_accrued_interest_payable_account_parameter = (
    interest_accrual_common.get_accrued_interest_payable_account_parameter
)

get_interest_accrual_precision = interest_accrual_common.get_accrual_precision_parameter
