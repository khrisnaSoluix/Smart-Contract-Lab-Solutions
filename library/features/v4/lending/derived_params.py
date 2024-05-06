# standard libs
from datetime import datetime
from decimal import Decimal
from typing import Optional

# features
import library.features.v4.common.utils as utils
import library.features.v4.lending.lending_addresses as lending_addresses
import library.features.v4.lending.lending_interfaces as lending_interfaces

# contracts api
from contracts_api import BalanceDefaultDict, NumberShape, Parameter, ParameterLevel

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

PARAM_TOTAL_OUTSTANDING_DEBT = "total_outstanding_debt"
PARAM_TOTAL_OUTSTANDING_PAYMENTS = "total_outstanding_payments"
PARAM_TOTAL_REMAINING_PRINCIPAL = "total_remaining_principal"
PARAM_PRINCIPAL_PAID_TO_DATE = "principal_paid_to_date"
PARAM_REMAINING_TERM = "remaining_term"

total_outstanding_debt_parameter = Parameter(
    name=PARAM_TOTAL_OUTSTANDING_DEBT,
    shape=NumberShape(min_value=0),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Remaining total balance on this account",
    display_name="Total Outstanding Debt",
)

total_outstanding_payments_parameter = Parameter(
    name=PARAM_TOTAL_OUTSTANDING_PAYMENTS,
    shape=NumberShape(min_value=0),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Remaining total payments to be made on this account",
    display_name="Total Outstanding Payments",
)

total_remaining_principal_parameter = Parameter(
    name=PARAM_TOTAL_REMAINING_PRINCIPAL,
    shape=NumberShape(min_value=0),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Remaining total principal balance on the account",
    display_name="Total Remaining Principal",
)

principal_paid_to_date_parameter = Parameter(
    name=PARAM_PRINCIPAL_PAID_TO_DATE,
    shape=NumberShape(min_value=0),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Principal paid so far on this account.",
    display_name="Principal Paid To Date",
)

remaining_term_parameter = Parameter(
    name=PARAM_REMAINING_TERM,
    shape=NumberShape(),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Remaining total term in months",
    display_name="Remaining Term In Months",
)

all_parameters = [
    total_outstanding_debt_parameter,
    total_outstanding_payments_parameter,
    total_remaining_principal_parameter,
    remaining_term_parameter,
]


def get_total_due_amount(
    balances: BalanceDefaultDict,
    denomination: str,
    precision: int = 2,
) -> Decimal:
    """
    Sums the balances across all due addresses
    :param balances: a dictionary of balances in the account
    :param denomination: the denomination of the balances to be summed
    :param precision: the number of decimal places to round to
    :return: due balance in Decimal
    """
    return utils.sum_balances(
        balances=balances,
        addresses=lending_addresses.REPAYMENT_HIERARCHY,
        denomination=denomination,
        decimal_places=precision,
    )


def get_total_outstanding_debt(
    balances: BalanceDefaultDict,
    denomination: str,
    precision: int = 2,
    debt_addresses: list[str] = lending_addresses.ALL_OUTSTANDING,
) -> Decimal:
    """
    Sums the balances across all outstanding debt addresses
    :param balances: a dictionary of balances in the account
    :param denomination: the denomination of the balances to be summed
    :param precision: the number of decimal places to round to
    :param debt_addresses: outstanding debt addresses
    :return: outstanding debt balance in Decimal
    """
    return utils.sum_balances(
        balances=balances,
        addresses=debt_addresses,
        denomination=denomination,
        decimal_places=precision,
    )


def get_total_remaining_principal(
    balances: BalanceDefaultDict,
    denomination: str,
    precision: int = 2,
) -> Decimal:
    """
    Sums the balances across all principal addresses
    :param balances: A dictionary of balances in the account
    :param denomination: The denomination of the balances to be summed
    :param precision: The number of decimal places to round to
    :return: The total principal remaining on the account
    """
    return utils.sum_balances(
        balances=balances,
        addresses=lending_addresses.ALL_PRINCIPAL,
        denomination=denomination,
        decimal_places=precision,
    )


def get_principal_paid_to_date(
    original_principal: Decimal,
    balances: BalanceDefaultDict,
    denomination: str,
    precision: int = 2,
) -> Decimal:
    """
    Returns the amount of the original principal paid off
    :param original_principal: the original principal amount
    :param balances: A dictionary of balances in the account
    :param denomination: The denomination of the remaining principal amount
    :param precision: The number of decimal places to round to, defaults to 2
    :return: The principal paid to date
    """
    return original_principal - get_total_remaining_principal(
        balances=balances,
        denomination=denomination,
        precision=precision,
    )


def get_remaining_term(
    vault: SmartContractVault,
    effective_datetime: datetime,
    amortisation_feature: lending_interfaces.Amortisation,
    interest_rate: Optional[lending_interfaces.InterestRate] = None,
    principal_adjustments: Optional[list[lending_interfaces.PrincipalAdjustment]] = None,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> int:
    return amortisation_feature.term_details(
        vault=vault,
        effective_datetime=effective_datetime,
        interest_rate=interest_rate,
        principal_adjustments=principal_adjustments,
        balances=balances,
        denomination=denomination,
    )[1]
