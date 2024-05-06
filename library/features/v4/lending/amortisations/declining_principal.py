# standard libs
import math
from datetime import datetime
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import Optional, Union

# features
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.lending.lending_addresses as lending_addresses
import library.features.v4.lending.lending_interfaces as lending_interfaces
import library.features.v4.lending.lending_parameters as lending_params
import library.features.v4.lending.term_helpers as term_helpers

# contracts api
from contracts_api import BalanceDefaultDict

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import (
    SmartContractVault,
    SuperviseeContractVault,
)


def is_declining_principal_loan(amortisation_method: str) -> bool:
    return amortisation_method.upper() == "DECLINING_PRINCIPAL"


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
    :param use_expected_term: if True, the remaining term is purely based on original and
        elapsed term, ignoring any adjustments etc. If false, it is calculated based on
        principal, interest rate and emi
    :param principal_amount: the principal amount used for amortisation
        If no value provided, the principal set on parameter level is used.
    :param interest_rate: interest rate feature, if no value is provided, 0 is used.
    :param principal_adjustments: features used to adjust the principal that is amortised
        If no value provided, no adjustment is made to the principal.
    :param balances: balances to use instead of the effective datetime balances
    :param denomination: denomination to use instead of the effective datetime parameter value
    :return: the elapsed and remaining term
    """

    original_total_term = int(
        utils.get_parameter(vault=vault, name=lending_params.PARAM_TOTAL_REPAYMENT_COUNT)
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

    principal_balance = utils.balance_at_coordinates(
        balances=balances,
        address=lending_addresses.PRINCIPAL,
        denomination=denomination,
    )

    elapsed = term_helpers.calculate_elapsed_term(balances=balances, denomination=denomination)

    # This is to handle the scenario where the loan has been fully repaid (as a result of an early
    # repayment or otherwise) but the account has been left open
    expected_remaining_term = (
        (original_total_term - elapsed) if principal_balance > Decimal("0") else 0
    )
    if use_expected_term:
        return elapsed, expected_remaining_term

    emi = utils.balance_at_coordinates(
        balances=balances,
        address=lending_addresses.EMI,
        denomination=denomination,
    )
    # emi can be 0 outside of activation if we've had to reset it (e.g. conversion) or if the loan
    # didn't originally require amortising (e.g. interest only period)
    if emi == 0:
        return elapsed, expected_remaining_term

    monthly_interest_rate = (
        interest_rate.get_monthly_interest_rate(
            vault=vault,
            effective_datetime=effective_datetime,
            balances=balances,
            denomination=denomination,
        )
        if interest_rate is not None
        else Decimal(0)
    )
    adjusted_principal = principal_balance + Decimal(
        sum(
            adjustment.calculate_principal_adjustment(
                vault=vault, balances=balances, denomination=denomination
            )
            for adjustment in principal_adjustments or []
        )
    )

    remaining = calculate_remaining_term(
        emi=emi,
        remaining_principal=adjusted_principal,
        monthly_interest_rate=monthly_interest_rate,
    )

    # We need to use min here because the calculated value will not handle scenarios where
    # the principal hasn't reduced but the elapsed term has increased, for example, during a
    # repayment holiday
    remaining = min(remaining, expected_remaining_term)

    return elapsed, remaining


# TODO: INC-9779 Refactor this function and term_details above to extract the common functionality
def supervisor_term_details(
    loan_vault: SuperviseeContractVault,
    main_vault: SuperviseeContractVault,
    effective_datetime: datetime,
    use_expected_term: bool = True,
    interest_rate: Optional[lending_interfaces.InterestRate] = None,
    principal_adjustments: Optional[list[lending_interfaces.SupervisorPrincipalAdjustment]] = None,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> tuple[int, int]:
    """Calculate the elapsed and remaining term for a loan when using a supervisor

    :param loan_vault: the supervisee vault object for the loan account
    :param main_vault: the supervisee vault object that principal adjustments are associated with
    :param effective_datetime: datetime as of which the calculations are performed
    :param use_expected_term: if True, the remaining term is purely based on original and
        elapsed term, ignoring any adjustments etc. If false, it is calculated based on
        principal, interest rate and emi
    :param principal_amount: the principal amount used for amortisation
        If no value provided, the principal set on parameter level is used.
    :param interest_rate: interest rate feature, if no value is provided, 0 is used.
    :param principal_adjustments: features used to adjust the principal that is amortised
        If no value provided, no adjustment is made to the principal.
    :param balances: balances to use instead of the effective datetime balances
    :param denomination: denomination to use instead of the effective datetime parameter value
    :return: the elapsed and remaining term
    """

    original_total_term = int(
        utils.get_parameter(vault=loan_vault, name=lending_params.PARAM_TOTAL_REPAYMENT_COUNT)
    )

    # this allows us to avoid fetching balances in activation hook
    if effective_datetime == loan_vault.get_account_creation_datetime():
        # in account activation, elapsed is 0 and the remaining term is the parameter value
        return 0, original_total_term

    if balances is None:
        balances = loan_vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    if denomination is None:
        denomination = utils.get_parameter(vault=loan_vault, name="denomination")

    principal_balance = utils.balance_at_coordinates(
        balances=balances,
        address=lending_addresses.PRINCIPAL,
        denomination=denomination,
    )

    elapsed = term_helpers.calculate_elapsed_term(balances=balances, denomination=denomination)

    # This is to handle the scenario where the loan has been fully repaid (as a result of an early
    # repayment or otherwise) but the account has been left open
    expected_remaining_term = (
        (original_total_term - elapsed) if principal_balance > Decimal("0") else 0
    )
    if use_expected_term:
        return elapsed, expected_remaining_term

    emi = utils.balance_at_coordinates(
        balances=balances,
        address=lending_addresses.EMI,
        denomination=denomination,
    )
    # emi can be 0 outside of activation if we've had to reset it (e.g. conversion) or if the loan
    # didn't originally require amortising (e.g. interest only period)
    if emi == 0:
        return elapsed, expected_remaining_term

    monthly_interest_rate = (
        interest_rate.get_monthly_interest_rate(
            vault=loan_vault,
            effective_datetime=effective_datetime,
            balances=balances,
            denomination=denomination,
        )
        if interest_rate is not None
        else Decimal(0)
    )
    adjusted_principal = principal_balance + Decimal(
        sum(
            adjustment.calculate_principal_adjustment(
                main_vault=main_vault,
                loan_vault=loan_vault,
                balances=balances,
                denomination=denomination,
            )
            for adjustment in principal_adjustments or []
        )
    )

    remaining = calculate_remaining_term(
        emi=emi,
        remaining_principal=adjusted_principal,
        monthly_interest_rate=monthly_interest_rate,
    )

    # We need to use min here because the calculated value will not handle scenarios where
    # the principal hasn't reduced but the elapsed term has increased, for example, during a
    # repayment holiday
    remaining = min(remaining, expected_remaining_term)

    return elapsed, remaining


def calculate_remaining_term(
    emi: Decimal,
    remaining_principal: Decimal,
    monthly_interest_rate: Decimal,
    decimal_places: int = 2,
    rounding: str = ROUND_HALF_UP,
) -> int:
    """
    The remaining term calculated using the amortisation formula
    math.log((EMI/(EMI - P*R)), (1+R)), where:

    EMI is the equated monthly instalment
    P is the remaining principal
    R is the monthly interest rate

    Note that, when the monthly interest rate R is 0, the remaining term
    is calculated using P / EMI. When the EMI is 0, this function will
    return 0.

    The term is rounded using specified arguments and then ceil'd to ensure that partial
    terms are treated as a full term (e.g. rounded remaining term as 16.4 results in 17)

    :param emi: The equated monthly instalment
    :param remaining_principal: The remaining principal
    :param monthly_interest_rate: The monthly interest rate
    :param decimal_places: The number of decimal places to round to
    :param rounding: The type of rounding strategy to use
    :return: The remaining term left on the loan
    """

    if emi == Decimal("0"):
        return 0

    remaining_term = (
        Decimal(
            math.log(
                (emi / (emi - (remaining_principal * monthly_interest_rate))),
                (1 + monthly_interest_rate),
            )
        )
        if monthly_interest_rate > Decimal("0")
        else remaining_principal / emi
    )

    # we use ceil to ensure that 'partial' terms, after rounding, are recognised as a full term
    return int(
        utils.round_decimal(
            amount=remaining_term, decimal_places=decimal_places, rounding=rounding
        ).to_integral_exact(rounding=ROUND_CEILING)
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
    Extracts relevant data required and calculates declining principal EMI.
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
    principal, interest_rate = _get_declining_principal_formula_terms(
        vault=vault,
        effective_datetime=effective_datetime,
        principal_amount=principal_amount,
        interest_calculation_feature=interest_calculation_feature,
    )

    _, remaining_term = term_details(
        vault=vault,
        effective_datetime=effective_datetime,
        use_expected_term=use_expected_term,
        interest_rate=interest_calculation_feature,
        principal_adjustments=principal_adjustments,
        balances=balances,
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

    return apply_declining_principal_formula(
        remaining_principal=principal, interest_rate=interest_rate, remaining_term=remaining_term
    )


def supervisor_calculate_emi(
    loan_vault: SuperviseeContractVault,
    main_vault: SuperviseeContractVault,
    effective_datetime: datetime,
    use_expected_term: bool = True,
    principal_amount: Optional[Decimal] = None,
    interest_calculation_feature: Optional[lending_interfaces.InterestRate] = None,
    principal_adjustments: Optional[list[lending_interfaces.SupervisorPrincipalAdjustment]] = None,
    balances: Optional[BalanceDefaultDict] = None,
) -> Decimal:
    """
    Extracts relevant data required and calculates declining principal EMI. Intended to be used
    with the supervisor due amount calculation feature
    :param loan_vault: vault object for which EMI must be calculated
    :param main_vault: the supervisee vault object that principal adjustments are associated with
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
    principal, interest_rate = _get_declining_principal_formula_terms(
        vault=loan_vault,
        effective_datetime=effective_datetime,
        principal_amount=principal_amount,
        interest_calculation_feature=interest_calculation_feature,
    )

    _, remaining_term = supervisor_term_details(
        loan_vault=loan_vault,
        main_vault=main_vault,
        effective_datetime=effective_datetime,
        use_expected_term=use_expected_term,
        interest_rate=interest_calculation_feature,
        principal_adjustments=principal_adjustments,
        balances=balances,
    )

    # An example of a principal adjustment being passed in here is the overpayments supervisor
    # principal adjustment interface. This needs to access balances from the loan_vault and the
    # overpayment preference parameter from the main_vault
    if principal_adjustments:
        denomination: str = utils.get_parameter(vault=main_vault, name="denomination")
        principal += Decimal(
            sum(
                adjustment.calculate_principal_adjustment(
                    loan_vault=loan_vault,
                    main_vault=main_vault,
                    balances=balances,
                    denomination=denomination,
                )
                for adjustment in principal_adjustments
            )
        )

    return apply_declining_principal_formula(
        remaining_principal=principal, interest_rate=interest_rate, remaining_term=remaining_term
    )


# extracted from EMI feature - duplication to be removed in subsequent diff
def apply_declining_principal_formula(
    remaining_principal: Decimal,
    interest_rate: Decimal,
    remaining_term: int,
    fulfillment_precision: int = 2,
    lump_sum_amount: Optional[Decimal] = None,
) -> Decimal:
    """
    Calculates the EMI according to the following formula:
    EMI = (P-(L/(1+R)^(N)))*R*(((1+R)^N)/((1+R)^N-1))
    P is principal remaining
    R is the interest rate, which should match the term unit (i.e. monthly rate if
    remaining term is also in months)
    N is term remaining
    L is the lump sum
    Formula can be used for a standard declining principal loan or a
    minimum repayment loan which includes a lump_sum_amount to be paid at the
    end of the term that is > 0.
    When the lump sum amount L is 0, the formula is reduced to:
    EMI = [P x R x (1+R)^N]/[(1+R)^N-1]
    :param remaining_principal: principal remaining
    :param interest_rate: interest rate appropriate for the term unit
    :param remaining_term: the number of integer term units remaining
    :param fulfillment_precision: precision needed for interest fulfillment
    :param lump_sum_amount: an optional one-off repayment amount
    :return: emi amount
    """
    lump_sum_amount = lump_sum_amount or Decimal("0")

    # the remaining term can be <= 0 when there is no more principal to amortise, but there is
    # still some due/overdue principal that keeps the loan open
    if remaining_term <= Decimal("0"):
        return remaining_principal
    # Handle division by zero error, when interest_rate is zero eg BNPL
    elif interest_rate == Decimal("0"):
        return utils.round_decimal(remaining_principal / remaining_term, fulfillment_precision)
    else:
        return utils.round_decimal(
            (remaining_principal - (lump_sum_amount / (1 + interest_rate) ** (remaining_term)))
            * interest_rate
            * ((1 + interest_rate) ** remaining_term)
            / ((1 + interest_rate) ** remaining_term - 1),
            fulfillment_precision,
        )


def _get_declining_principal_formula_terms(
    vault: Union[SmartContractVault, SuperviseeContractVault],
    effective_datetime: datetime,
    principal_amount: Optional[Decimal] = None,
    interest_calculation_feature: Optional[lending_interfaces.InterestRate] = None,
) -> tuple[Decimal, Decimal]:

    principal = (
        utils.get_parameter(vault=vault, name="principal")
        if principal_amount is None
        else principal_amount
    )

    interest_rate = (
        Decimal(0)
        if not interest_calculation_feature
        else interest_calculation_feature.get_monthly_interest_rate(
            vault=vault, effective_datetime=effective_datetime
        )
    )

    return principal, interest_rate


AmortisationFeature = lending_interfaces.Amortisation(
    calculate_emi=calculate_emi, term_details=term_details, override_final_event=False
)

SupervisorAmortisationFeature = lending_interfaces.SupervisorAmortisation(
    calculate_emi=supervisor_calculate_emi,
    term_details=supervisor_term_details,
    override_final_event=False,
)
