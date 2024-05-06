# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

# features
import library.features.v4.common.accruals as accruals
import library.features.v4.common.interest_accrual_common as interest_accrual_common
import library.features.v4.common.utils as utils
import library.features.v4.lending.interest_accrual as interest_accrual
import library.features.v4.lending.lending_interfaces as lending_interfaces

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    AccountIdShape,
    BalanceCoordinate,
    BalanceDefaultDict,
    BalancesFilter,
    BalancesObservation,
    BalancesObservationFetcher,
    DefinedDateTime,
    NumberShape,
    Parameter,
    ParameterLevel,
    Phase,
    Posting,
    RelativeDateTime,
    Shift,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

ACCRUED_INTEREST_RECEIVABLE = interest_accrual_common.ACCRUED_INTEREST_RECEIVABLE
INTEREST_DUE = "INTEREST_DUE"


# Fetchers
ACCRUED_INTEREST_EFF_FETCHER_ID = "ACCRUED_INTEREST_EFFECTIVE_DATETIME_FETCHER"
accrued_interest_eff_fetcher = BalancesObservationFetcher(
    fetcher_id=ACCRUED_INTEREST_EFF_FETCHER_ID,
    at=DefinedDateTime.EFFECTIVE_DATETIME,
    filter=BalancesFilter(addresses=[ACCRUED_INTEREST_RECEIVABLE]),
)

ACCRUED_INTEREST_ONE_MONTH_AGO_FETCHER_ID = "ACCRUED_INTEREST_ONE_MONTH_AGO_FETCHER"
accrued_interest_one_month_ago_fetcher = BalancesObservationFetcher(
    fetcher_id=ACCRUED_INTEREST_ONE_MONTH_AGO_FETCHER_ID,
    at=RelativeDateTime(origin=DefinedDateTime.EFFECTIVE_DATETIME, shift=Shift(months=-1)),
    filter=BalancesFilter(addresses=[ACCRUED_INTEREST_RECEIVABLE]),
)

# Parameters
PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = (
    interest_accrual.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
)
PARAM_INTEREST_RECEIVED_ACCOUNT = "interest_received_account"
PARAM_APPLICATION_PRECISION = "application_precision"

application_precision_param = Parameter(
    name=PARAM_APPLICATION_PRECISION,
    level=ParameterLevel.TEMPLATE,
    description="Number of decimal places accrued interest is rounded to when applying interest.",
    display_name="Interest Application Precision",
    shape=NumberShape(max_value=15, step=1),
    default_value=Decimal(2),
)

interest_received_account_param = Parameter(
    name=PARAM_INTEREST_RECEIVED_ACCOUNT,
    level=ParameterLevel.TEMPLATE,
    description="Internal account for interest received balance.",
    display_name="Interest Received Account",
    shape=AccountIdShape(),
    default_value="INTEREST_RECEIVED",
)
account_parameters = [interest_received_account_param]


def apply_interest(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    previous_application_datetime: datetime,
    balances_at_application: Optional[BalanceDefaultDict] = None,
) -> list[Posting]:
    application_internal_account = get_application_internal_account(vault=vault)
    application_interest_address = INTEREST_DUE
    accrual_internal_account = interest_accrual.get_accrual_internal_account(vault=vault)
    denomination = utils.get_parameter(vault, "denomination")
    application_precision = get_application_precision(vault=vault)

    effective_datetime_observation: BalancesObservation = vault.get_balances_observation(
        fetcher_id=ACCRUED_INTEREST_EFF_FETCHER_ID
    )
    one_month_ago_observation: BalancesObservation = vault.get_balances_observation(
        fetcher_id=ACCRUED_INTEREST_ONE_MONTH_AGO_FETCHER_ID
    )

    interest_application_amounts = _get_interest_to_apply(
        balances_at_application=effective_datetime_observation.balances,
        balances_one_repayment_period_ago=one_month_ago_observation.balances,
        denomination=denomination,
        application_precision=application_precision,
        effective_datetime=effective_datetime,
        previous_application_datetime=previous_application_datetime,
    )

    return accruals.accrual_application_postings(
        customer_account=vault.account_id,
        denomination=denomination,
        application_amount=interest_application_amounts.total_rounded,
        accrual_amount=interest_application_amounts.emi_accrued
        + interest_application_amounts.non_emi_accrued,
        accrual_customer_address=ACCRUED_INTEREST_RECEIVABLE,
        accrual_internal_account=accrual_internal_account,
        application_customer_address=application_interest_address,
        application_internal_account=application_internal_account,
        payable=False,
    )


def _interest_amounts(
    balances: BalanceDefaultDict,
    denomination: str,
    precision: int = 2,
    rounding: str = ROUND_HALF_UP,
) -> tuple[Decimal, Decimal]:
    """
    Determine the amount of interest in balances, un-rounded and rounded
    :param balances: balances for the account that interest is being applied on
    :param denomination: denomination of the accrued interest to apply
    :param precision: the number of decimal places to round to
    :param rounding: the Decimal rounding strategy to use
    :return: the un-rounded and rounded amounts
    """

    accrued_amount = balances[
        BalanceCoordinate(
            ACCRUED_INTEREST_RECEIVABLE,
            DEFAULT_ASSET,
            denomination,
            phase=Phase.COMMITTED,
        )
    ].net

    return accrued_amount, utils.round_decimal(
        accrued_amount, decimal_places=precision, rounding=rounding
    )


def _get_interest_to_apply(
    *,
    balances_at_application: BalanceDefaultDict,
    balances_one_repayment_period_ago: BalanceDefaultDict,
    denomination: str,
    application_precision: int,
    effective_datetime: datetime,
    previous_application_datetime: datetime,
) -> lending_interfaces.InterestAmounts:
    effective_unrounded, effective_rounded = _interest_amounts(
        balances=balances_at_application,
        denomination=denomination,
        precision=application_precision,
    )

    # if previous_application_datetime < 1 month ago then all interest accrued is emi interest
    if effective_datetime - relativedelta(months=1) < previous_application_datetime:
        one_period_ago_unrounded, one_period_ago_rounded = Decimal("0"), Decimal("0")
    else:
        one_period_ago_unrounded, one_period_ago_rounded = _interest_amounts(
            balances=balances_one_repayment_period_ago,
            denomination=denomination,
            precision=application_precision,
        )

    return lending_interfaces.InterestAmounts(
        emi_accrued=effective_unrounded - one_period_ago_unrounded,
        emi_rounded_accrued=effective_rounded - one_period_ago_rounded,
        non_emi_accrued=one_period_ago_unrounded,
        non_emi_rounded_accrued=one_period_ago_rounded,
        total_rounded=effective_rounded,
    )


def get_interest_to_apply(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    previous_application_datetime: datetime,
    balances_at_application: Optional[BalanceDefaultDict] = None,
    balances_one_repayment_period_ago: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    application_precision: Optional[int] = None,
) -> lending_interfaces.InterestAmounts:
    """Determine the interest amounts for application, handling emi/non-emi considerations.

    :param vault: vault object for the account with interest to apply
    :param effective_datetime: the effective datetime for interest application
    :param previous_application_datetime: the previous datetime of interest application
    :param balances_at_application: balances at the time of application, before application has
    been processed. If None, fetched using the ACCRUED_INTEREST_EFF_FETCHER_ID fetcher
    :param balances_one_repayment_period_ago: balances one repayment period before application. If
    None, fetched using the ACCRUED_INTEREST_ONE_MONTH_AGO_FETCHER_ID fetcher
    :param denomination: the denomination to use for accrual. If None, the latest value of the
    `denomination` parameter is used.
    :param application_precision: number of places that accrued interest is rounded to before
    application. If None, the latest value of the PARAM_APPLICATION_PRECISION parameter is used.
    :return: the interest amounts
    """

    if balances_at_application is None:
        balances_at_application = vault.get_balances_observation(
            fetcher_id=ACCRUED_INTEREST_EFF_FETCHER_ID
        ).balances

    if balances_one_repayment_period_ago is None:
        balances_one_repayment_period_ago = vault.get_balances_observation(
            fetcher_id=ACCRUED_INTEREST_ONE_MONTH_AGO_FETCHER_ID
        ).balances

    if application_precision is None:
        application_precision = get_application_precision(vault=vault)
    if denomination is None:
        denomination = utils.get_parameter(vault=vault, name="denomination")

    return _get_interest_to_apply(
        balances_at_application=balances_at_application,
        balances_one_repayment_period_ago=balances_one_repayment_period_ago,
        denomination=denomination,
        application_precision=application_precision,
        effective_datetime=effective_datetime,
        previous_application_datetime=previous_application_datetime,
    )


# Putting this method inside interest_application may seem a little unintuitive. Given how we model
# accrual repayments, putting it anywhere would else introduces worse dependency-related problems
def repay_accrued_interest(
    vault: SmartContractVault,
    repayment_amount: Decimal,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
    application_customer_address: str = DEFAULT_ADDRESS,
) -> list[Posting]:
    """Creates postings to repay accrued interest. This is typically for overpayment scenarios.
    In order to recognise interest income, repaying accrued interest is modelled as
    interest application + immediate repayment.

    :param vault: the vault object for the account holding the accrued interest to be repaid
    :param repayment_amount: the repayment amount that can be allocated to accrued interest
    :param denomination: repayment denomination. If None, the latest value of the
    `denomination` parameter is used.
    :param balances: account balances to determine repayment allocation. If None, fetched using the
    ACCRUED_INTEREST_EFF_FETCHER_ID fetcher
    :param application_customer_address: the address to use on the customer account for interest
    application. Applying to the DEFAULT_ADDRESS will rebalance the repayment that credits
    DEFAULT_ADDRESS, which makes this equivalent to applying the interest and repaying the applied
    interest
    :return: the postings for repaying accrued interest. Empty list if no repayment is possible
    (e.g. repayment amount is insufficient, or no accrued interest to repay)
    """

    if repayment_amount <= 0:
        return []

    if denomination is None:
        denomination = utils.get_parameter(vault=vault, name="denomination")

    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=ACCRUED_INTEREST_EFF_FETCHER_ID
        ).balances

    accrual_internal_account = interest_accrual.get_accrual_internal_account(vault=vault)
    application_internal_account = get_application_internal_account(vault=vault)
    application_precision = get_application_precision(vault=vault)

    postings: list[Posting] = []

    accrued_amount, rounded_accrued_amount = _interest_amounts(
        balances=balances,
        denomination=denomination,
        precision=application_precision,
    )

    if rounded_accrued_amount <= repayment_amount:
        application_amount = rounded_accrued_amount
        accrual_amount = accrued_amount
    else:
        # e.g. repaying 10.12 when accrued interest is 11.145 should apply 10.12, with
        # 1.025 accrued interest remaining
        application_amount = repayment_amount
        accrual_amount = repayment_amount

    if application_amount > 0:
        postings.extend(
            accruals.accrual_application_postings(
                customer_account=vault.account_id,
                denomination=denomination,
                application_amount=application_amount,
                accrual_amount=accrual_amount,
                accrual_customer_address=ACCRUED_INTEREST_RECEIVABLE,
                accrual_internal_account=accrual_internal_account,
                application_customer_address=application_customer_address,
                application_internal_account=application_internal_account,
                payable=False,
            )
        )

    return postings


def get_application_precision(vault: SmartContractVault) -> int:
    return int(utils.get_parameter(vault=vault, name=PARAM_APPLICATION_PRECISION))


def get_application_internal_account(vault: SmartContractVault) -> str:
    application_internal_account: str = utils.get_parameter(
        vault=vault, name=PARAM_INTEREST_RECEIVED_ACCOUNT
    )
    return application_internal_account


InterestApplication = lending_interfaces.InterestApplication(
    apply_interest=apply_interest,
    get_interest_to_apply=get_interest_to_apply,
    get_application_precision=get_application_precision,
)
