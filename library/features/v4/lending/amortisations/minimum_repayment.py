# standard libs
from datetime import datetime
from decimal import Decimal
from typing import Optional

# features
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.lending.amortisations.declining_principal as declining_principal
import library.features.v4.lending.lending_interfaces as lending_interfaces
import library.features.v4.lending.lending_parameters as lending_parameters
import library.features.v4.lending.term_helpers as term_helpers

# contracts api
from contracts_api import BalanceDefaultDict

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

AMORTISATION_METHOD = "MINIMUM_REPAYMENT_WITH_BALLOON_PAYMENT"


def is_minimum_repayment_loan(amortisation_method: str) -> bool:
    return amortisation_method.upper() == AMORTISATION_METHOD


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
    Extracts relevant data required and calculates minimum repayment EMI.
    :param vault: Vault object
    :param effective_datetime: the datetime as of which the calculation is performed
    :param use_expected_term: if True, the remaining term is purely based on original and
        elapsed term, ignoring any adjustments etc. If false, it is calculated based on
        principal, interest rate and emi
    :param principal_amount: the principal amount used for amortisation
        If no value provided, the principal set on parameter level is used.
    :param interest_calculation_feature: interest calculation feature, if no value is
        provided, 0 is used.
    :param principal_adjustments: features used to adjust the principal that is amortised
        If no value provided, no adjustment is made to the principal.
    :param balances: balances to use instead of the effective datetime balances
    :return: emi amount
    """
    # Check if this is a balloon payment loan with a fixed EMI or a fixed Balloon payment.
    static_emi = utils.get_parameter(vault=vault, name="balloon_emi_amount", is_optional=True)

    # A fixed EMI that is defined at activation.
    # If there exists a predefined static EMI, then skip the needed calculations.
    # If the value is unset then assume that the EMI is not static
    if static_emi:
        return static_emi

    # Set assume that there is no balloon payment if the value is unset.
    balloon_payment_amount = utils.get_parameter(
        vault=vault, name="balloon_payment_amount", is_optional=True, default_value=Decimal("0")
    )

    # Static Balloon payment case
    # Underlying formula used is EMI = (P-(L/(1+R)^(N)))*R*(((1+R)^N)/((1+R)^N-1))
    # this is the same as the minimum repayment formula (which uses a zeroed Lump Sum).
    # - L is the Lump Sum (Balloon Payment) amount.
    # - P is the Principal Remaining
    # - N is the Term remaining
    # - R is the interest rate to apply

    interest_rate = (
        Decimal(0)
        if not interest_calculation_feature
        else interest_calculation_feature.get_monthly_interest_rate(
            vault=vault, effective_datetime=effective_datetime
        )
    )
    principal = (
        utils.get_parameter(vault=vault, name="principal")
        if principal_amount is None
        else principal_amount
    )

    if principal_adjustments:
        denomination: str = utils.get_parameter(vault=vault, name="denomination")
        principal += Decimal(
            sum(
                adjustment.calculate_principal_adjustment(
                    vault=vault, balances=balances, denomination=denomination
                )
                for adjustment in principal_adjustments
            )
        )

    _, remaining_term = term_details(
        vault=vault,
        use_expected_term=use_expected_term,
        effective_datetime=effective_datetime,
        interest_rate=interest_calculation_feature,
        principal_adjustments=principal_adjustments,
        balances=balances,
    )

    return declining_principal.apply_declining_principal_formula(
        remaining_principal=principal,
        interest_rate=interest_rate,
        remaining_term=remaining_term,
        lump_sum_amount=balloon_payment_amount,
    )


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
    Using a counter based approach to simplify the logic required
    when addressing static or derived EMI Repayment.

    :param vault: the vault object for the loan account
    :param effective_datetime: datetime as of which the calculations are performed
    :param use_expected_term: Not used but required for the interface
    :param interest_rate: Not used but required for the interface
    :param principal_adjustments: Not used but required for the interface
    :param balances: balances to use instead of the effective datetime balances
    :param denomination: denomination to use instead of the effective datetime parameter value
    :return: the elapsed and remaining term
    """

    original_total_term = int(
        utils.get_parameter(vault=vault, name=lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT)
    )

    # this allows us to avoid fetching balances in activation hook
    if effective_datetime == vault.get_account_creation_datetime():
        # in account activation, elapsed is 0 and the remaining term is the parameter value
        return 0, original_total_term

    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    if denomination is None:
        denomination = utils.get_parameter(vault=vault, name="denomination")

    elapsed = term_helpers.calculate_elapsed_term(balances=balances, denomination=denomination)
    expected_remaining_term = original_total_term - elapsed

    return elapsed, expected_remaining_term


AmortisationFeature = lending_interfaces.Amortisation(
    calculate_emi=calculate_emi, term_details=term_details, override_final_event=True
)
