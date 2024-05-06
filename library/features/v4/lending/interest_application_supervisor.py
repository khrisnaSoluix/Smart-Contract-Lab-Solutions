# This module implements interest application differently for supervisors, due to the different
# implementation required for interest accrual. See interest_accrual_supervisor.py for more
# information

# standard libs
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

# features
import library.features.v4.common.accruals as accruals
import library.features.common.fetchers as fetchers
import library.features.v4.common.interest_accrual_common as interest_accrual_common
import library.features.v4.common.utils as utils
import library.features.v4.lending.interest_accrual_supervisor as interest_accrual_supervisor
import library.features.v4.lending.lending_interfaces as lending_interfaces

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    AccountIdShape,
    BalanceCoordinate,
    BalanceDefaultDict,
    BalancesFilter,
    BalancesObservationFetcher,
    DefinedDateTime,
    NumberShape,
    Parameter,
    ParameterLevel,
    Phase,
    Posting,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import (
    SmartContractVault,
    SuperviseeContractVault,
)

ACCRUAL_EVENT = interest_accrual_common.ACCRUAL_EVENT
ACCRUED_INTEREST_RECEIVABLE = interest_accrual_common.ACCRUED_INTEREST_RECEIVABLE
NON_EMI_ACCRUED_INTEREST_RECEIVABLE = (
    interest_accrual_supervisor.NON_EMI_ACCRUED_INTEREST_RECEIVABLE
)
INTEREST_DUE = "INTEREST_DUE"


# Fetchers
ACCRUED_INTEREST_EFF_FETCHER_ID = "ACCRUED_INTEREST_EFFECTIVE_DATETIME_FETCHER"
accrued_interest_eff_fetcher = BalancesObservationFetcher(
    fetcher_id=ACCRUED_INTEREST_EFF_FETCHER_ID,
    at=DefinedDateTime.EFFECTIVE_DATETIME,
    filter=BalancesFilter(
        addresses=[ACCRUED_INTEREST_RECEIVABLE, NON_EMI_ACCRUED_INTEREST_RECEIVABLE]
    ),
)

# Parameters
PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = (
    interest_accrual_supervisor.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
)
PARAM_INTEREST_RECEIVED_ACCOUNT = "interest_received_account"
PARAM_APPLICATION_PRECISION = "application_precision"

application_precision_param = Parameter(
    name=PARAM_APPLICATION_PRECISION,
    level=ParameterLevel.TEMPLATE,
    description="Number of decimal places accrued interest is rounded to when applying interest.",
    display_name="Interest Accrual Precision",
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
    vault: SmartContractVault,
    effective_datetime: datetime,
    previous_application_datetime: datetime,
    balances_at_application: Optional[BalanceDefaultDict] = None,
) -> list[Posting]:
    application_internal_account = utils.get_parameter(vault, PARAM_INTEREST_RECEIVED_ACCOUNT)
    application_interest_address = INTEREST_DUE
    accrual_internal_account = utils.get_parameter(vault, PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT)
    denomination = utils.get_parameter(vault, "denomination")
    application_precision: int = utils.get_parameter(vault=vault, name=PARAM_APPLICATION_PRECISION)

    if balances_at_application is None:
        balances_at_application = vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances

    interest_application_amounts = _get_interest_to_apply(
        balances=balances_at_application,
        denomination=denomination,
        application_precision=application_precision,
    )

    return accruals.accrual_application_postings(
        customer_account=vault.account_id,
        denomination=denomination,
        application_amount=interest_application_amounts.emi_rounded_accrued,
        accrual_amount=interest_application_amounts.emi_accrued,
        accrual_customer_address=ACCRUED_INTEREST_RECEIVABLE,
        accrual_internal_account=accrual_internal_account,
        application_customer_address=application_interest_address,
        application_internal_account=application_internal_account,
        payable=False,
    ) + accruals.accrual_application_postings(
        customer_account=vault.account_id,
        denomination=denomination,
        # the below application amount deals with any rounding issues where
        # round(emi_accrued_amount) + round(non_emi_accrued_amount) !=
        # round(emi_accrued_amount + non_emi_accrued_amount)
        # we want the case where we apply
        # round(emi_accrued_amount + non_emi_accrued_amount) across both postings
        application_amount=interest_application_amounts.total_rounded
        - interest_application_amounts.emi_rounded_accrued,
        accrual_amount=interest_application_amounts.non_emi_accrued,
        accrual_customer_address=NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
        accrual_internal_account=accrual_internal_account,
        application_customer_address=application_interest_address,
        application_internal_account=application_internal_account,
        payable=False,
    )


def _get_interest_to_apply(
    balances: BalanceDefaultDict, denomination: str, application_precision: int
) -> lending_interfaces.InterestAmounts:
    emi_accrued_amount, emi_rounded_accrued_amount = _get_emi_interest_to_apply(
        balances=balances,
        denomination=denomination,
        precision=application_precision,
    )

    non_emi_accrued_amount, non_emi_rounded_accrued_amount = _get_non_emi_interest_to_apply(
        balances=balances,
        denomination=denomination,
        precision=application_precision,
    )

    total_rounded_amount = utils.round_decimal(
        amount=emi_accrued_amount + non_emi_accrued_amount,
        decimal_places=application_precision,
        rounding=ROUND_HALF_UP,
    )

    return lending_interfaces.InterestAmounts(
        emi_accrued=emi_accrued_amount,
        emi_rounded_accrued=emi_rounded_accrued_amount,
        non_emi_accrued=non_emi_accrued_amount,
        non_emi_rounded_accrued=non_emi_rounded_accrued_amount,
        total_rounded=total_rounded_amount,
    )


def get_interest_to_apply(
    vault: SuperviseeContractVault,
    effective_datetime: datetime,
    previous_application_datetime: datetime,
    balances_at_application: Optional[BalanceDefaultDict] = None,
    balances_one_repayment_period_ago: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    application_precision: Optional[int] = None,
) -> lending_interfaces.InterestAmounts:
    """Determine the interest amounts for application, handling emi/non-emi considerations.

    :param vault: vault object for the account with interest to apply
    :param effective_datetime: not used but required by the interface signature
    :param previous_application_datetime: not used but required by the interface signature
    :param balances_at_application: balances to extract current accrued amounts from.
    :param balances_one_repayment_period_ago: not used but required by the interface signature,
    since we have the separate addresses needed available in balances_at_application.
    :param denomination: accrual denomination. Only pass in to override the feature's default
    fetching
    :param application_precision: number of places that accrued interest is rounded to before
    application. Only pass in to override the feature's default fetching
    :return: the interest amounts
    """

    if balances_at_application is None:
        balances_mapping = vault.get_balances_timeseries()
        balances_at_application = utils.get_balance_default_dict_from_mapping(
            mapping=balances_mapping,
            effective_datetime=effective_datetime,
        )
    if application_precision is None:
        application_precision = utils.get_parameter(vault=vault, name=PARAM_APPLICATION_PRECISION)
    if denomination is None:
        denomination = utils.get_parameter(vault=vault, name="denomination")

    return _get_interest_to_apply(
        balances=balances_at_application,
        denomination=denomination,
        application_precision=application_precision,
    )


def _get_emi_interest_to_apply(
    balances: BalanceDefaultDict,
    denomination: str,
    accrual_addresses: Optional[list[str]] = None,
    precision: int = 2,
    rounding: str = ROUND_HALF_UP,
) -> tuple[Decimal, Decimal]:
    """
    Determine the amount of interest to apply that should be included in EMI, before and after
    rounding.
    :param balances: balances for the account that interest is being applied on
    :param denomination: denomination of the accrued interest to apply
    :param accrual_address: balance addresses to consider. Defaults to
    and ACCRUED_INTEREST_RECEIVABLE, which excludes non-emi interest
    :param precision: the number of decimal places to round to
    :param rounding: the Decimal rounding strategy to use
    :return: the unrounded and rounded amounts
    """

    accrual_addresses = accrual_addresses or [ACCRUED_INTEREST_RECEIVABLE]
    accrued_amount = Decimal(
        sum(
            balances[
                BalanceCoordinate(
                    accrual_address,
                    DEFAULT_ASSET,
                    denomination,
                    phase=Phase.COMMITTED,
                )
            ].net
            for accrual_address in accrual_addresses
        )
    )

    return accrued_amount, utils.round_decimal(
        accrued_amount, decimal_places=precision, rounding=rounding
    )


def _get_non_emi_interest_to_apply(
    balances: BalanceDefaultDict,
    denomination: str,
    accrual_addresses: Optional[list[str]] = None,
    precision: int = 2,
    rounding: str = ROUND_HALF_UP,
) -> tuple[Decimal, Decimal]:
    """
    Determine the amount of interest to apply that should not be included in EMI, before and after
    rounding.
    :param balances: balances for the account that interest is being applied on
    :param denomination: denomination of the accrued interest to apply
    :param accrual_address: balance addresses to consider. Defaults to
    and NON_EMI_ACCRUED_INTEREST_RECEIVABLE, which excludes non-emi interest
    :param precision: the number of decimal places to round to
    :param rounding: the Decimal rounding strategy to use
    :return: the unrounded and rounded amounts
    """

    accrual_addresses = accrual_addresses or [NON_EMI_ACCRUED_INTEREST_RECEIVABLE]
    accrued_amount = Decimal(
        sum(
            balances[
                BalanceCoordinate(
                    accrual_address,
                    DEFAULT_ASSET,
                    denomination,
                    phase=Phase.COMMITTED,
                )
            ].net
            for accrual_address in accrual_addresses
        )
    )

    return accrued_amount, utils.round_decimal(
        accrued_amount, decimal_places=precision, rounding=rounding
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
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances

    accrual_internal_account: str = utils.get_parameter(
        vault=vault, name=PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
    )
    application_internal_account: str = utils.get_parameter(
        vault=vault, name=PARAM_INTEREST_RECEIVED_ACCOUNT
    )
    application_precision: int = utils.get_parameter(vault=vault, name=PARAM_APPLICATION_PRECISION)

    repayment_amount_remaining = repayment_amount

    postings: list[Posting] = []

    for interest_address, interest_to_apply in (
        (NON_EMI_ACCRUED_INTEREST_RECEIVABLE, _get_non_emi_interest_to_apply),
        (ACCRUED_INTEREST_RECEIVABLE, _get_emi_interest_to_apply),
    ):
        accrued_amount, rounded_accrued_amount = interest_to_apply(
            balances=balances,
            denomination=denomination,
            precision=application_precision,
        )

        if rounded_accrued_amount <= repayment_amount_remaining:
            application_amount = rounded_accrued_amount
            accrual_amount = accrued_amount
        else:
            # e.g. repaying 10.12 for accrued interest is 11.145 should apply 10.12, with
            # 1.025 accrued interest remaining
            application_amount = repayment_amount_remaining
            accrual_amount = repayment_amount_remaining

        if application_amount > 0:
            repayment_amount_remaining -= application_amount
            postings.extend(
                accruals.accrual_application_postings(
                    customer_account=vault.account_id,
                    denomination=denomination,
                    application_amount=application_amount,
                    accrual_amount=accrual_amount,
                    accrual_customer_address=interest_address,
                    accrual_internal_account=accrual_internal_account,
                    application_customer_address=application_customer_address,
                    application_internal_account=application_internal_account,
                    payable=False,
                )
            )
        if repayment_amount_remaining == 0:
            return postings

    return postings


def get_application_precision(vault: SmartContractVault) -> int:
    return int(utils.get_parameter(vault=vault, name=PARAM_APPLICATION_PRECISION))


interest_application_interface = lending_interfaces.InterestApplication(
    apply_interest=apply_interest,
    get_interest_to_apply=get_interest_to_apply,
    get_application_precision=get_application_precision,
)
