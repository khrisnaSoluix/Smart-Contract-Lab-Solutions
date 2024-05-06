# standard libs
from datetime import datetime
from decimal import Decimal
from typing import Optional

# features
import library.features.v4.common.fees as fees
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.lending.interest_application as interest_application
import library.features.v4.lending.lending_addresses as lending_addresses
import library.features.v4.lending.lending_interfaces as lending_interfaces
import library.features.v4.lending.lending_parameters as lending_parameters
import library.features.v4.lending.term_helpers as term_helpers

# contracts api
from contracts_api import BalanceDefaultDict, Posting

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# Parameters - TODO Should move these to a common location
PARAM_DENOMINATION = "denomination"
PARAM_FIXED_INTEREST_RATE = "fixed_interest_rate"
PARAM_PRINCIPAL = "principal"


def is_rule_of_78_loan(amortisation_method: str) -> bool:
    return amortisation_method.upper() == "RULE_OF_78"


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

    return elapsed, expected_remaining_term


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

    fixed_interest_rate = (
        Decimal(0)
        if not interest_calculation_feature
        else interest_calculation_feature.get_annual_interest_rate(
            vault=vault, effective_datetime=effective_datetime
        )
    )

    total_term = int(
        utils.get_parameter(vault=vault, name=lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT)
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

    application_precision = utils.get_parameter(
        vault=vault, name=interest_application.PARAM_APPLICATION_PRECISION
    )

    total_loan_interest = calculate_non_accruing_loan_total_interest(
        original_principal=principal,
        annual_interest_rate=fixed_interest_rate,
        total_term=total_term,
        precision=application_precision,
    )

    return utils.round_decimal(
        (principal + total_loan_interest) / total_term, application_precision
    )


def apply_interest(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    previous_application_datetime: datetime,
    balances_at_application: Optional[BalanceDefaultDict] = None,
) -> list[Posting]:
    """
    Creates the postings needed to apply interest for a loan using rule of 78 loan amortisation
    :param vault: vault object
    """
    application_internal_account: str = utils.get_parameter(
        vault, interest_application.PARAM_INTEREST_RECEIVED_ACCOUNT
    )
    application_interest_address: str = interest_application.INTEREST_DUE
    denomination: str = utils.get_parameter(vault, PARAM_DENOMINATION)
    application_precision = interest_application.get_application_precision(vault=vault)
    effective_balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances

    interest_application_amounts = get_interest_to_apply(
        vault=vault,
        effective_datetime=effective_datetime,
        previous_application_datetime=previous_application_datetime,
        balances_at_application=effective_balances,
        denomination=denomination,
        application_precision=application_precision,
    )

    return fees.fee_postings(
        customer_account_id=vault.account_id,
        customer_account_address=application_interest_address,
        denomination=denomination,
        amount=interest_application_amounts.emi_rounded_accrued,
        internal_account=application_internal_account,
    )


def get_interest_to_apply(
    vault: SmartContractVault,
    effective_datetime: datetime,
    previous_application_datetime: datetime,
    balances_at_application: Optional[BalanceDefaultDict] = None,
    balances_one_repayment_period_ago: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    application_precision: Optional[int] = None,
) -> lending_interfaces.InterestAmounts:
    """
    Determines the interest amount for application using rule of 78 amortisation.
    For flat and rule of 78 interest we don't have concept of emi vs non emi interest as the
    accrued amount is calculated for the month at the end of the month, instead of daily accruals.
    Hence, we do not use some of the args passed in for this implementation of the interface.

    :param vault: vault object for the account with interest to apply
    :param effective_datetime: not used but required by the interface signature
    :param previous_application_datetime: not used but required by the interface signature
    :param balances_at_application: balances to extract current accrued amounts from. Only pass in
    to override the feature's default fetching
    :param balances_one_repayment_period_ago: not used but required by the interface signature
    :param denomination: accrual denomination. Only pass in to override the feature's default
    fetching
    :param application_precision: number of places that interest is rounded to during application.
     Only pass in to override the feature's default fetching
    :return: the interest amounts
    """

    if balances_at_application is None:
        balances_at_application = vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    if application_precision is None:
        application_precision = interest_application.get_application_precision(vault=vault)
    if denomination is None:
        denomination = utils.get_parameter(vault=vault, name=PARAM_DENOMINATION)

    principal: Decimal = utils.get_parameter(vault=vault, name=PARAM_PRINCIPAL)
    total_term = int(
        utils.get_parameter(vault=vault, name=lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT)
    )

    # Calculating the remaining term again here instead of passing it from the due amount
    # calculation feature as only rule of 78 amortisation method would require remaining term
    elapsed = term_helpers.calculate_elapsed_term(
        balances=balances_at_application, denomination=denomination
    )
    term_remaining = total_term - elapsed

    # Rule of 78 only supports fixed_interest loans, therefore we always use the
    # fixed_interest_rate
    fixed_interest_rate: Decimal = utils.get_parameter(vault=vault, name=PARAM_FIXED_INTEREST_RATE)

    total_interest = calculate_non_accruing_loan_total_interest(
        original_principal=principal,
        annual_interest_rate=fixed_interest_rate,
        total_term=total_term,
        precision=application_precision,
    )

    rule_of_78_denominator = _get_sum_1_to_N(total_term)

    interest_due = _calculate_interest_due(
        total_interest=total_interest,
        total_term=total_term,
        term_remaining=term_remaining,
        denominator=rule_of_78_denominator,
        application_precision=application_precision,
    )

    return lending_interfaces.InterestAmounts(
        emi_accrued=Decimal("0"),
        emi_rounded_accrued=interest_due,
        non_emi_accrued=Decimal("0"),
        non_emi_rounded_accrued=Decimal("0"),
        total_rounded=interest_due,
    )


def _calculate_interest_due(
    total_interest: Decimal,
    total_term: int,
    term_remaining: int,
    denominator: int,
    application_precision: int,
) -> Decimal:
    """
    Returns the amount of interest due for a rule of 78 loan accounting for any rounding issues
    on the final event.
    :param total_interest: total interest to be paid during the loan's tenure
    :param term_remaining: number of repayments remaining on the loan
    :param denominator: rule of 78 denominator,
    calculated by summing all integers from 1 to the total_term of the loan.
    :param application_precision: number of places that interest is rounded to during application.
    """
    if term_remaining == 1:
        return _calculate_final_month_interest(
            total_interest=total_interest,
            total_term=total_term,
            rule_of_78_denominator=denominator,
            application_precision=application_precision,
        )

    return utils.round_decimal(
        total_interest * term_remaining / denominator,
        application_precision,
    )


def _calculate_final_month_interest(
    total_interest: Decimal,
    total_term: int,
    rule_of_78_denominator: int,
    application_precision: int,
) -> Decimal:
    """
    The final month interest will be equal to:
    total_interest - SUM(interest_month_n) from n = 0 to n = total_term - 1, where interest_month_n
    is given by total_interest * (total_term - n) / rule_of_78_denominator

    """
    return total_interest - Decimal(
        sum(
            utils.round_decimal(
                amount=(total_interest * (total_term - n) / rule_of_78_denominator),
                decimal_places=application_precision,
            )
            for n in range(0, total_term - 1)
        )
    )


def _get_sum_1_to_N(N: int) -> int:
    """
    Returns the sum of integers from 1 to N.
    This is used to calculate the interest portion of a rule of 78 loan.
    :param N: The integer that we will sum to
    """
    return int(N * (N + 1) / 2)


# TODO Extract into common place for flat interest to use
def calculate_non_accruing_loan_total_interest(
    original_principal: Decimal,
    annual_interest_rate: Decimal,
    total_term: int,
    precision: int,
) -> Decimal:
    """
    Returns the total loan interest for a flat interest or rule of 78 amortised loan
    :param original_principal: principal of the loan at loan start
    :param annual_interest_rate: yearly interest rate of the loan
    :param total_term: total term of the loan
    :param precision: number of places that interest is rounded to before application.
    """
    return utils.round_decimal(
        original_principal
        * utils.yearly_to_monthly_rate(yearly_rate=annual_interest_rate)
        * Decimal(total_term),
        precision,
    )


InterestApplication = lending_interfaces.InterestApplication(
    apply_interest=apply_interest,
    get_interest_to_apply=get_interest_to_apply,
    get_application_precision=interest_application.get_application_precision,
)

AmortisationFeature = lending_interfaces.Amortisation(
    calculate_emi=calculate_emi,
    term_details=term_details,
    override_final_event=False,
)
