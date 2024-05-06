# standard libs
from datetime import datetime
from decimal import Decimal
from typing import Optional

# features
import library.features.v4.lending.lending_interfaces as lending_interfaces
import library.features.v4.lending.term_helpers as term_helpers

# contracts api
from contracts_api import BalanceDefaultDict

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

AMORTISATION_METHOD = "INTEREST_ONLY"


def is_interest_only_loan(amortisation_method: str) -> bool:
    return amortisation_method.upper() == AMORTISATION_METHOD


def term_details(
    vault: SmartContractVault,
    effective_datetime: datetime,
    use_expected_term: bool = True,
    interest_rate: Optional[lending_interfaces.InterestRate] = None,
    principal_adjustments: Optional[list[lending_interfaces.PrincipalAdjustment]] = None,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> tuple[int, int]:
    """Calculate the elapsed and remaining term for a loan

    :param vault: the vault object for the loan account
    :param effective_datetime: datetime as of which the calculations are performed
    :param use_expected_term: Not used but required for the interface
    :param interest_rate: Not used but required for the interface
    :param principal_adjustments: Not used but required for the interface
    :param balances: balances to use instead of the effective datetime balances
    :param denomination: denomination to use instead of the effective datetime parameter value
    :return: the elapsed and remaining term
    """
    return term_helpers.calculate_term_details_from_counter(
        vault=vault,
        effective_datetime=effective_datetime,
        balances=balances,
        denomination=denomination,
    )


def calculate_emi(
    vault: SmartContractVault,
    effective_datetime: datetime,
    use_expected_term: bool = True,
    principal_amount: Optional[Decimal] = None,
    interest_calculation_feature: Optional[lending_interfaces.InterestRate] = None,
    principal_adjustments: Optional[list[lending_interfaces.PrincipalAdjustment]] = None,
    balances: Optional[BalanceDefaultDict] = None,
) -> Decimal:
    """
    This signature is required to meet the interface definition only
    :param vault: Vault object
    :param effective_datetime: the datetime as of which the calculation is performed
    :param use_expected_term: Not used but required for the interface
    :param principal_amount: the principal amount used for amortisation
        If no value provided, the principal set on parameter level is used.
    :param interest_calculation_feature: interest calculation feature, if no value is
        provided, 0 is used.
    :param principal_adjustments: features used to adjust the principal that is amortised
        If no value provided, no adjustment is made to the principal.
    :param balances: balances to use instead of the effective datetime balances
    :return: emi amount
    """

    return Decimal("0")


AmortisationFeature = lending_interfaces.Amortisation(
    calculate_emi=calculate_emi, term_details=term_details, override_final_event=True
)
