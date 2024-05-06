# standard libs
from datetime import datetime
from decimal import Decimal
from typing import Optional

# features
import library.features.v4.common.events as events
import library.features.v4.common.utils as utils
import library.features.v4.lending.lending_addresses as lending_addresses
import library.features.v4.lending.lending_interfaces as lending_interfaces

# contracts api
from contracts_api import (
    BalanceDefaultDict,
    CustomInstruction,
    NumberShape,
    Parameter,
    ParameterLevel,
    Posting,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

PARAM_EQUATED_INSTALMENT_AMOUNT = "equated_instalment_amount"

equated_instalment_amount_parameter = Parameter(
    name=PARAM_EQUATED_INSTALMENT_AMOUNT,
    shape=NumberShape(min_value=0, step=Decimal("0.01")),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="The amount customer is expected to pay per repayment period.",
    display_name="Equated Instalment Amount",
)

derived_parameters = [equated_instalment_amount_parameter]


def amortise(
    vault: SmartContractVault,
    effective_datetime: datetime,
    amortisation_feature: lending_interfaces.Amortisation,
    principal_amount: Optional[Decimal] = None,
    interest_calculation_feature: Optional[lending_interfaces.InterestRate] = None,
    principal_adjustments: Optional[list[lending_interfaces.PrincipalAdjustment]] = None,
    balances: Optional[BalanceDefaultDict] = None,
    event: Optional[str] = events.ACCOUNT_ACTIVATION,
) -> list[CustomInstruction]:
    """
    Amortises a loan by calculating EMI and creating a custom instruction to update the balance
    value at the EMI address. Suitable for initial amortisation, and reamortisation if the
    `balances` argument is populated.

    :param vault: Vault object
    :param effective_datetime: effective dt for calculating the emi
    :param amortisation_feature: contains the emi calculation method for the desired amortisation
    :param principal_amount: the principal amount used for amortisation
        If no value provided, the amortisation feature calculate_emi method is expected to set
        principal amount to the value set on parameter level.
    :param interest_calculation_feature: an interest calculation feature
    :param principal_adjustments: features used to adjust the principal that is amortised
        If no value provided, no adjustment is made to the principal.
    :param event: event string to be included in the CustomInstruction instruction_details.
        If not provided, value defaults to ACCOUNT_ACTIVATION.
    :param balances: balances used to calculate emi and determine whether postings are required to
    update it. If balances are None, emi and elapsed term both assumed to be 0. This
    is suitable for scenarios such as initial amortisation on account activation
    :return: list of custom instructions, empty if no changes to the EMI
    """
    updated_emi = amortisation_feature.calculate_emi(
        vault=vault,
        effective_datetime=effective_datetime,
        principal_amount=principal_amount,
        interest_calculation_feature=interest_calculation_feature,
        principal_adjustments=principal_adjustments,
        balances=balances,
    )

    denomination: str = utils.get_parameter(
        vault, name="denomination", at_datetime=effective_datetime
    )
    if balances is None:
        current_emi = Decimal("0")
    else:
        current_emi = utils.balance_at_coordinates(
            balances=balances, address=lending_addresses.EMI, denomination=denomination
        )

    update_emi_postings = update_emi(
        account_id=vault.account_id,
        denomination=denomination,
        current_emi=current_emi,
        updated_emi=updated_emi,
    )
    if not update_emi_postings:
        return []

    return [
        CustomInstruction(
            postings=update_emi_postings,
            instruction_details={
                "description": f"Updating EMI to {updated_emi}",
                "event": f"{event}",
            },
        )
    ]


def update_emi(
    account_id: str, denomination: str, current_emi: Decimal, updated_emi: Decimal
) -> list[Posting]:

    emi_delta = current_emi - updated_emi
    if emi_delta == Decimal("0"):
        return []

    if emi_delta < Decimal("0"):
        credit_address = lending_addresses.INTERNAL_CONTRA
        debit_address = lending_addresses.EMI
        emi_delta = abs(emi_delta)
    else:
        credit_address = lending_addresses.EMI
        debit_address = lending_addresses.INTERNAL_CONTRA

    return utils.create_postings(
        amount=emi_delta,
        debit_account=account_id,
        debit_address=debit_address,
        credit_account=account_id,
        credit_address=credit_address,
        denomination=denomination,
    )


def get_expected_emi(
    balances: BalanceDefaultDict, denomination: str, decimal_places: Optional[int] = 2
) -> Decimal:
    return utils.balance_at_coordinates(
        balances=balances,
        address=lending_addresses.EMI,
        denomination=denomination,
        decimal_places=decimal_places,
    )
