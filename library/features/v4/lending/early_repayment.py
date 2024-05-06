# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from decimal import Decimal
from typing import Optional

# features
import library.features.v4.common.fees as fees
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.lending.derived_params as derived_params
import library.features.v4.lending.lending_addresses as lending_addresses
import library.features.v4.lending.lending_interfaces as lending_interfaces

# contracts api
from contracts_api import (
    AccountIdShape,
    BalanceDefaultDict,
    CustomInstruction,
    NumberShape,
    Parameter,
    ParameterLevel,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# Parameters
PARAM_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT = "early_repayment_fee_income_account"
PARAM_EARLY_REPAYMENT_FLAT_FEE = "early_repayment_flat_fee"
PARAM_EARLY_REPAYMENT_FEE_RATE = "early_repayment_fee_rate"

# Derived Parameters
PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT = "total_early_repayment_amount"

early_repayment_fee_income_account_param = Parameter(
    name=PARAM_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT,
    shape=AccountIdShape(),
    level=ParameterLevel.TEMPLATE,
    description="Internal account for early repayment fee income balance.",
    display_name="Early Repayment Fee Income Account",
    default_value="EARLY_REPAYMENT_FEE_INCOME",
)
early_repayment_flat_fee_param = Parameter(
    name=PARAM_EARLY_REPAYMENT_FLAT_FEE,
    level=ParameterLevel.TEMPLATE,
    description="Flat fee to charge for an early repayment. "
    "Typically this would be used instead of Early Repayment Fee Rate, "
    "otherwise they will both be added together.",
    display_name="Early Repayment Flat Fee",
    shape=NumberShape(min_value=0),
    default_value=Decimal("0"),
)
early_repayment_fee_rate_param = Parameter(
    name=PARAM_EARLY_REPAYMENT_FEE_RATE,
    level=ParameterLevel.TEMPLATE,
    description="This rate will be used to calculate a fee to be charged for an early repayment, "
    "calculated as a percentage of the remaining principal. "
    "Typically this would be used instead of Early Repayment Flat Fee, "
    "otherwise they will both be added together.",
    display_name="Early Repayment Fee Rate",
    shape=NumberShape(min_value=0),
    default_value=Decimal("0.01"),
)
total_early_repayment_amount_parameter = Parameter(
    name=PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT,
    shape=NumberShape(),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Total early repayment amount required to fully repay and close the account",
    display_name="Total Early Repayment Amount",
)
parameters = [
    early_repayment_fee_income_account_param,
    early_repayment_flat_fee_param,
    early_repayment_fee_rate_param,
    total_early_repayment_amount_parameter,
]


def is_posting_an_early_repayment(
    vault: SmartContractVault,
    repayment_amount: Decimal,
    early_repayment_fees: Optional[list[lending_interfaces.EarlyRepaymentFee]],
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    precision: int = 2,
) -> bool:
    """
    Determine whether the repayment amount is equal to the total amount required to fully pay off
    and close the account. A repayment posting amount will be less than 0 since this is for
    asset/lending products.

    :param vault: vault object for the relevant account
    :param repayment_amount: the amount being repaid
    :param early_repayment_fees: early repayment fee features
    :param balances: balances to base calculations on
    :param denomination: denomination of the relevant loan
    :param precision: the number of decimal places to round to
    :return: true if the repayment amount matches the required amount to do a full early repayment
    """
    if repayment_amount >= Decimal("0"):
        return False

    balances = _get_balances(vault=vault, balances=balances)
    denomination = _get_denomination(vault=vault, denomination=denomination)

    # If this is called after the final due calculation event, principal will be zero
    # and therefore any repayment posting would not be for an early repayment.
    if _is_zero_principal(balances=balances, denomination=denomination):
        return False

    return abs(repayment_amount) == get_total_early_repayment_amount(
        vault=vault,
        denomination=denomination,
        early_repayment_fees=early_repayment_fees,
        balances=balances,
        precision=precision,
    )


def get_total_early_repayment_amount(
    vault: SmartContractVault,
    early_repayment_fees: Optional[list[lending_interfaces.EarlyRepaymentFee]],
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    precision: int = 2,
    debt_addresses: list[str] = lending_addresses.ALL_OUTSTANDING,
    check_for_outstanding_accrued_interest_on_zero_principal: bool = False,
) -> Decimal:
    """
    Get the exact repayment amount required for a full early repayment.

    :param vault: vault object for the relevant account
    :param early_repayment_fees: early repayment fee features
    :param balances: balances to base calculations on
    :param denomination: denomination of the relevant loan
    :param precision: the number of decimal places to round to
    :param debt_addresses: outstanding debt addresses
    :param check_for_outstanding_accrued_interest_on_zero_principal: if outstanding balances on
    loans that have zero principal should count as early repayment
    :return: the exact repayment amount required for a full early repayment
    """
    balances = _get_balances(vault=vault, balances=balances)
    denomination = _get_denomination(vault=vault, denomination=denomination)

    # If this is called after the final due calculation event, principal will be zero
    # and therefore any repayment posting would not be for an early repayment.
    # However, if an overpayment has resulted in zero principal, there may still be accrued interest
    # that has not yet been applied
    if not check_for_outstanding_accrued_interest_on_zero_principal and _is_zero_principal(
        balances=balances, denomination=denomination
    ):
        return utils.round_decimal(Decimal("0"), precision)

    return _get_sum_of_early_repayment_fees_and_outstanding_debt(
        vault=vault,
        early_repayment_fees=early_repayment_fees or [],
        balances=balances,
        denomination=denomination,
        precision=precision,
        debt_addresses=debt_addresses,
    )


def get_early_repayment_flat_fee(
    vault: SmartContractVault,
    balances: Optional[BalanceDefaultDict] = None,  # only needed to satisfy the interface signature
    denomination: Optional[str] = None,  # only needed to satisfy the interface signature
    precision: int = 2,
) -> Decimal:
    """
    Get the early repayment flat fee amount from the parameter value. To be used as a
    get_early_repayment_fee_amount callable for an EarlyRepaymentFee interface.

    :param vault: vault object for the relevant account
    :param balances: only needed to satisfy the interface signature
    :param denomination: only needed to satisfy the interface signature
    :param precision: the number of decimal places to round to
    :return: the flat fee amount
    """
    early_repayment_flat_fee = utils.get_parameter(vault=vault, name=PARAM_EARLY_REPAYMENT_FLAT_FEE)
    return utils.round_decimal(early_repayment_flat_fee, precision)


def calculate_early_repayment_percentage_fee(
    vault: SmartContractVault,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    precision: int = 2,
) -> Decimal:
    """
    Calculate the early repayment fee using the rate from the Early Repayment Fee Rate parameter
    with the total remaining principal. To be used as a get_early_repayment_fee_amount callable for
    an EarlyRepaymentFee interface.

    :param vault: vault object for the relevant account
    :param balances: balances to base calculations on
    :param denomination: denomination of the relevant loan
    :param precision: the number of decimal places to round to
    :return: the percentage fee amount
    """
    balances = _get_balances(vault=vault, balances=balances)
    denomination = _get_denomination(vault=vault, denomination=denomination)

    total_remaining_principal = derived_params.get_total_remaining_principal(
        balances=balances,
        denomination=denomination,
    )
    early_repayment_fee_rate = utils.get_parameter(vault=vault, name=PARAM_EARLY_REPAYMENT_FEE_RATE)
    return utils.round_decimal(total_remaining_principal * early_repayment_fee_rate, precision)


def charge_early_repayment_fee(
    vault: SmartContractVault,
    account_id: str,
    amount_to_charge: Decimal,
    fee_name: str,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Handle the early repayment fee within post posting, returning the associated posting
    instructions for the fee. To be used as a charge_early_repayment_fee callable for
    an EarlyRepaymentFee interface.

    :param vault: vault object for the relevant account
    :param account_id: id of the customer account
    :param amount_to_charge: the amount to charge for the fee
    :param fee_name: the name of the early repayment fee type
    :param denomination: denomination of the relevant loan
    :return: custom instruction to handle the charge of the fee
    """
    denomination = _get_denomination(vault=vault, denomination=denomination)
    early_repayment_fee_income_account: str = utils.get_parameter(
        vault=vault,
        name=PARAM_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT,
    )
    return fees.fee_custom_instruction(
        customer_account_id=account_id,
        denomination=denomination,
        amount=amount_to_charge,
        internal_account=early_repayment_fee_income_account,
        instruction_details={
            "description": f"Early Repayment Fee: {fee_name}",
        },
    )


def _is_zero_principal(
    denomination: str,
    balances: BalanceDefaultDict,
) -> bool:
    """
    Return true if there is a zero principal balance.

    :param denomination: denomination of the relevant loan
    :param balances: balances to base calculations on
    :return: true if there is a zero principal balance
    """
    return utils.sum_balances(
        balances=balances,
        addresses=[lending_addresses.PRINCIPAL],
        denomination=denomination,
    ) <= Decimal("0")


def _get_denomination(vault: SmartContractVault, denomination: Optional[str] = None) -> str:
    """
    Get the denomination of the account, allowing for a None to be passed in.

    :param vault: vault object for the relevant account
    :param denomination: denomination of the relevant loan
    :return: the denomination
    """
    return (
        utils.get_parameter(vault=vault, name="denomination")
        if denomination is None
        else denomination
    )


def _get_balances(
    vault: SmartContractVault, balances: Optional[BalanceDefaultDict] = None
) -> BalanceDefaultDict:
    """
    Return the balances that are passed in or get the live balances of the account.

    :param vault: vault object for the relevant account
    :param balances: balances to base calculations on
    :return: the balances
    """
    return (
        vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances
        if balances is None
        else balances
    )


def _get_sum_of_early_repayment_fees_and_outstanding_debt(
    vault: SmartContractVault,
    early_repayment_fees: list[lending_interfaces.EarlyRepaymentFee],
    balances: BalanceDefaultDict,
    denomination: str,
    precision: int,
    debt_addresses: list[str],
) -> Decimal:
    """
    Get the exact repayment amount required for a full early repayment.

    :param vault: vault object for the relevant account
    :param early_repayment_fees: early repayment fee features
    :param balances: balances to base calculations on
    :param denomination: denomination of the relevant loan
    :param precision: the number of decimal places to round to
    :param debt_addresses: outstanding debt addresses
    :return: the exact repayment amount required for a full early repayment
    """
    early_repayment_fees_sum = Decimal("0")

    for early_repayment_fee in early_repayment_fees:
        early_repayment_fees_sum += early_repayment_fee.get_early_repayment_fee_amount(
            vault=vault,
            balances=balances,
            denomination=denomination,
            precision=precision,
        )

    total_outstanding_debt = derived_params.get_total_outstanding_debt(
        balances=balances, denomination=denomination, debt_addresses=debt_addresses
    )
    return total_outstanding_debt + early_repayment_fees_sum


EarlyRepaymentFlatFee = lending_interfaces.EarlyRepaymentFee(
    get_early_repayment_fee_amount=get_early_repayment_flat_fee,
    charge_early_repayment_fee=charge_early_repayment_fee,
    fee_name="Flat Fee",
)

EarlyRepaymentPercentageFee = lending_interfaces.EarlyRepaymentFee(
    get_early_repayment_fee_amount=calculate_early_repayment_percentage_fee,
    charge_early_repayment_fee=charge_early_repayment_fee,
    fee_name="Percentage Fee",
)
