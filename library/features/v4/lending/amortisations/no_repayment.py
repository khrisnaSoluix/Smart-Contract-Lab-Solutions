# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Optional

# features
import library.features.v4.common.utils as utils
import library.features.v4.lending.lending_interfaces as lending_interfaces
import library.features.v4.lending.lending_parameters as lending_params

# contracts api
from contracts_api import BalanceDefaultDict

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

AMORTISATION_METHOD = "NO_REPAYMENT"


def is_no_repayment_loan(amortisation_method: str) -> bool:
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
    No Repayment amortisation will always return 0 EMI

    """
    return Decimal(0)


def term_details(
    vault: SmartContractVault,
    effective_datetime: datetime,
    use_expected_term: bool = True,
    interest_rate: Optional[lending_interfaces.InterestRate] = None,
    principal_adjustments: Optional[list[lending_interfaces.PrincipalAdjustment]] = None,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> tuple[int, int]:
    """Calculate the elapsed and remaining term for a loan. Given that this is a no repayment loan,
    the term is based on the difference in current datetime to the account opening time.

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

    # Given that a monthly due amount calculation will not be run, and no term counter populated.
    # we will fallback to a term calculation based on the execution time relative
    # to the loan start time.
    original_total_term = int(
        utils.get_parameter(vault=vault, name=lending_params.PARAM_TOTAL_REPAYMENT_COUNT)
    )
    loan_start_date = vault.get_account_creation_datetime()

    # in the event the loan has not started, do not use negative values
    effective_datetime = max(loan_start_date, effective_datetime)

    delta = relativedelta(effective_datetime, loan_start_date)
    delta_months = delta.years * 12 + delta.months
    remaining_months = original_total_term - delta_months

    # in the event for some reason the time is past the original term time,
    # cap this value at the original term
    if remaining_months < 0:
        return original_total_term, 0
    return delta_months, remaining_months


def get_balloon_payment_datetime(vault: SmartContractVault) -> datetime:
    balloon_payment_start_date = vault.get_account_creation_datetime()
    original_total_term = int(
        utils.get_parameter(vault=vault, name=lending_params.PARAM_TOTAL_REPAYMENT_COUNT)
    )
    balloon_payment_delta_days = int(
        utils.get_parameter(
            vault=vault, name="balloon_payment_days_delta", is_optional=True, default_value=0
        )
    )
    return balloon_payment_start_date + relativedelta(
        days=balloon_payment_delta_days, months=original_total_term
    )


AmortisationFeature = lending_interfaces.Amortisation(
    calculate_emi=calculate_emi, term_details=term_details, override_final_event=True
)
