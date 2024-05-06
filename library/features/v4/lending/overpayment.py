# standard libs
from datetime import datetime
from decimal import Decimal
from typing import Optional, Union

# features
import library.features.v4.common.fees as fees
import library.features.common.fetchers as fetchers
import library.features.v4.common.interest_accrual_common as interest_accrual_common
import library.features.v4.common.utils as utils
import library.features.v4.lending.interest_application as interest_application
import library.features.v4.lending.lending_addresses as lending_addresses
import library.features.v4.lending.lending_interfaces as lending_interfaces

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    AccountIdShape,
    BalanceDefaultDict,
    BalancesFilter,
    BalancesObservationFetcher,
    CustomInstruction,
    DefinedDateTime,
    NumberShape,
    Override,
    Parameter,
    ParameterLevel,
    Phase,
    Posting,
    Rejection,
    RejectionReason,
    RelativeDateTime,
    ScheduledEventHookArguments,
    SupervisorScheduledEventHookArguments,
    Tside,
    UnionItem,
    UnionItemValue,
    UnionShape,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import (
    SmartContractVault,
    SuperviseeContractVault,
)

# feature addresses
ACCRUED_EXPECTED_INTEREST = "ACCRUED_EXPECTED_INTEREST"
EMI_PRINCIPAL_EXCESS = "EMI_PRINCIPAL_EXCESS"
OVERPAYMENT = "OVERPAYMENT"

OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER = "OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER"
# Principal as if no overpayments had occurred
EXPECTED_PRINCIPAL = [lending_addresses.PRINCIPAL, OVERPAYMENT, EMI_PRINCIPAL_EXCESS]

# For use when accruing expected interest on a daily basis
EXPECTED_INTEREST_ACCRUAL_EOD_FETCHER_ID = "EXPECTED_INTEREST_ACCRUAL_EOD_FETCHER"
expected_interest_eod_fetcher = BalancesObservationFetcher(
    fetcher_id=EXPECTED_INTEREST_ACCRUAL_EOD_FETCHER_ID,
    at=RelativeDateTime(
        origin=DefinedDateTime.EFFECTIVE_DATETIME, find=Override(hour=0, minute=0, second=0)
    ),
    filter=BalancesFilter(
        addresses=EXPECTED_PRINCIPAL
        + [
            # we must have this to make elapsed term accurate in the interest rate calculation
            lending_addresses.DUE_CALCULATION_EVENT_COUNTER,
        ]
    ),
)

# For use when interacting with effective datetime tracker balances
OVERPAYMENT_TRACKER_EFF_FETCHER_ID = "OVERPAYMENT_TRACKER_EFF_FETCHER"
overpayment_tracker_eff_fetcher = BalancesObservationFetcher(
    fetcher_id=OVERPAYMENT_TRACKER_EFF_FETCHER_ID,
    at=DefinedDateTime.EFFECTIVE_DATETIME,
    filter=BalancesFilter(
        addresses=[
            ACCRUED_EXPECTED_INTEREST,
            OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
        ]
    ),
)

# constants
REDUCE_EMI = "reduce_emi"
REDUCE_TERM = "reduce_term"

# parameters
PARAM_OVERPAYMENT_FEE_RATE = "overpayment_fee_rate"
PARAM_OVERPAYMENT_FEE_INCOME_ACCOUNT = "overpayment_fee_income_account"
PARAM_OVERPAYMENT_IMPACT_PREFERENCE = "overpayment_impact_preference"
overpayment_fee_rate_param = Parameter(
    name=PARAM_OVERPAYMENT_FEE_RATE,
    shape=NumberShape(min_value=Decimal("0"), max_value=Decimal("1"), step=Decimal("0.0001")),
    level=ParameterLevel.TEMPLATE,
    description="Percentage fee charged on the overpayment amount.",
    display_name="Overpayment Fee Rate",
    default_value=Decimal("0.05"),
)

overpayment_fee_income_account_param = Parameter(
    name=PARAM_OVERPAYMENT_FEE_INCOME_ACCOUNT,
    level=ParameterLevel.TEMPLATE,
    description="Internal account for overpayment fee income balance.",
    display_name="Overpayment Fee Income Account",
    shape=AccountIdShape(),
    default_value="OVERPAYMENT_FEE_INCOME",
)
overpayment_impact_preference_param = Parameter(
    name=PARAM_OVERPAYMENT_IMPACT_PREFERENCE,
    shape=UnionShape(
        items=[
            UnionItem(key=REDUCE_EMI, display_name="Reduce EMI"),
            UnionItem(key=REDUCE_TERM, display_name="Reduce Term"),
        ]
    ),
    level=ParameterLevel.TEMPLATE,
    description="Defines how to handle an overpayment: "
    "Reduce EMI but preserve the term."
    "Reduce term but preserve monthly repayment amount.",
    display_name="Overpayment Impact Preference",
    default_value=UnionItemValue(key=REDUCE_TERM),
)
fee_parameters = [overpayment_fee_rate_param, overpayment_fee_income_account_param]


def get_max_overpayment_fee(
    fee_rate: Decimal,
    balances: BalanceDefaultDict,
    denomination: str,
    precision: int = 2,
    principal_address: str = lending_addresses.PRINCIPAL,
) -> Decimal:
    """
    The maximum overpayment fee is equal to the maximum_overpayment_amount * overpayment_fee_rate,

    Maximum Overpayment Amount Proof:
        X = maximum_overpayment_amount
        R = overpayment_fee_rate
        P = remaining_principal
        F = overpayment_fee

        overpayment_fee = overpayment_amount * overpayment_fee_rate
        principal_repaid = overpayment_amount - overpayment_fee
        maximum_overpayment_amount is when principal_repaid == remaining_principal, therefore

        P = X - F
        but F = X*R
        => P = X - XR => X(1-R)
        and so:
        X = P / (1-R)
        and so F_max = PR / (1-R)
    """
    if fee_rate >= 1:
        return Decimal("0")

    principal = utils.balance_at_coordinates(
        balances=balances, address=principal_address, denomination=denomination
    )
    maximum_overpayment = utils.round_decimal(
        amount=(principal / (1 - fee_rate)), decimal_places=precision
    )

    overpayment_fee = get_overpayment_fee(
        principal_repaid=maximum_overpayment,
        overpayment_fee_rate=fee_rate,
        precision=precision,
    )

    return overpayment_fee


def get_overpayment_fee(
    principal_repaid: Decimal, overpayment_fee_rate: Decimal, precision: int
) -> Decimal:
    """Determines the overpayment fee for a given amount of principal being repaid

    :param principal_repaid: the amount of principal repaid by the repayment
    :param overpayment_fee_rate: the percentage of principal to include in the fee. Must be
    < 1, or 0 is returned
    :param precision: decimal places to round the fee to
    :return: the overpayment fee
    """
    if overpayment_fee_rate >= 1:
        return Decimal("0")
    return utils.round_decimal(
        amount=(principal_repaid * overpayment_fee_rate), decimal_places=precision
    )


def charge_overpayment_fee_as_penalty(
    vault: SmartContractVault, overpayment_amount: Decimal, denomination: str, precision: int
) -> list[CustomInstruction]:
    overpayment_fee_rate = get_overpayment_fee_rate_parameter(vault=vault)
    overpayment_fee_income_account = get_overpayment_fee_income_account_parameter(vault=vault)

    overpayment_fee = get_overpayment_fee(
        principal_repaid=overpayment_amount,
        overpayment_fee_rate=overpayment_fee_rate,
        precision=precision,
    )
    overpayment_fee_postings = get_overpayment_fee_postings(
        overpayment_fee=overpayment_fee,
        denomination=denomination,
        customer_account_id=vault.account_id,
        customer_account_address=lending_addresses.PENALTIES,
        internal_account=overpayment_fee_income_account,
    )

    if overpayment_fee_postings:
        return [
            CustomInstruction(
                postings=overpayment_fee_postings,
                instruction_details=utils.standard_instruction_details(
                    description=f"Charge {overpayment_fee=} on {overpayment_amount=}",
                    event_type="CHARGE_OVERPAYMENT_FEE",
                    gl_impacted=True,
                ),
                override_all_restrictions=True,
            )
        ]

    return []


def get_overpayment_fee_postings(
    overpayment_fee: Decimal,
    denomination: str,
    customer_account_id: str,
    customer_account_address: str,
    internal_account: str,
) -> list[Posting]:
    return fees.fee_postings(
        customer_account_id=customer_account_id,
        customer_account_address=customer_account_address,
        denomination=denomination,
        amount=overpayment_fee,
        internal_account=internal_account,
    )


def is_posting_an_overpayment(
    vault: SmartContractVault,
    repayment_amount: Decimal,
    denomination: str,
    fetcher_id: str = fetchers.LIVE_BALANCES_BOF_ID,
) -> bool:
    if repayment_amount >= 0:
        return False

    balances: BalanceDefaultDict = vault.get_balances_observation(fetcher_id=fetcher_id).balances
    due_amount = get_total_due_amount(balances=balances, denomination=denomination)
    return abs(repayment_amount) > due_amount


def validate_overpayment_across_supervisees(
    main_vault: SuperviseeContractVault,
    repayment_amount: Decimal,
    denomination: str,
    all_supervisee_balances: list[BalanceDefaultDict],
    rounding_precision: int = 2,
) -> Optional[Rejection]:
    """Rejects repayments if the repayment amount across all supervisees exceeds
    the total outstanding amount + the maximum overpayment amount

    :param main_vault: The vault object that stores the overpayment fee rate parameter
    :param repayment_amount: The repayment amount
    :param denomination: The denomination of the loan
    :param all_supervisee_balances: All of the supervisee balances used
    to validate the repayment
    :param rounding_precision: The rounding precision for the maximum overpayment
    amount. Defaults to 2
    :return: A rejection if the repayment amount exceeds the total
    outstanding amount + maximum overpayment amount, otherwise None
    """

    overpayment_fee_rate = get_overpayment_fee_rate_parameter(vault=main_vault)

    merged_supervisee_balances = BalanceDefaultDict()
    for balance in all_supervisee_balances:
        merged_supervisee_balances += balance

    max_overpayment_fee = get_max_overpayment_fee(
        fee_rate=overpayment_fee_rate,
        balances=merged_supervisee_balances,
        denomination=denomination,
    )

    total_outstanding_amount = utils.sum_balances(
        balances=merged_supervisee_balances,
        addresses=lending_addresses.ALL_OUTSTANDING_SUPERVISOR,
        denomination=denomination,
        decimal_places=rounding_precision,
    )

    max_overpayment_amount = utils.round_decimal(
        amount=max_overpayment_fee + total_outstanding_amount, decimal_places=rounding_precision
    )

    if repayment_amount > max_overpayment_amount:
        return Rejection(
            message=f"The repayment amount {repayment_amount} {denomination} "
            "exceeds the total maximum repayment amount of "
            f"{max_overpayment_amount} {denomination}.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

    return None


# TODO - this should be renamed as it is a bit misleading as it does not validate
# all criteria for an overpayment (checks if posting is > total debt)
def validate_overpayment(
    vault: SmartContractVault,
    repayment_amount: Decimal,
    denomination: str,
    fetcher_id: str = fetchers.LIVE_BALANCES_BOF_ID,
) -> Optional[Rejection]:
    """Rejects repayments if the amount exceeds total owed, including Principal, + overpayment fee

    :param vault: Vault object for the account being credited by the posting
    :param repayment_amount: the repayment amount. Expected to be negative as this function is for
    Tside.ASSET products.
    :param denomination: denomination of the loan
    :param fetcher_id: id of the fetcher to use, defaults to fetchers.LIVE_BALANCES_BOF_ID, which
    may not be suitable if used outside of pre_posting_hook
    :return: An optional rejection, only non-None if the amount repaid exceeds total owed + fee
    """

    if repayment_amount >= 0:
        return None

    max_overpayment_amount = get_max_overpayment_amount(
        vault=vault,
        denomination=denomination,
        fetcher_id=fetcher_id,
    )

    # use abs() here since a credit (repayment) is net -ve for Tside.ASSET
    if abs(repayment_amount) > max_overpayment_amount:
        return Rejection(
            message="Cannot pay more than is owed.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None


def get_max_overpayment_amount(
    vault: SmartContractVault,
    denomination: str,
    fetcher_id: str = fetchers.LIVE_BALANCES_BOF_ID,
) -> Decimal:
    overpayment_fee_rate = get_overpayment_fee_rate_parameter(vault=vault)
    balances: BalanceDefaultDict = vault.get_balances_observation(fetcher_id=fetcher_id).balances
    total_outstanding_debt = get_total_outstanding_debt(
        balances=balances, denomination=denomination
    )
    max_overpayment_fee = get_max_overpayment_fee(
        fee_rate=overpayment_fee_rate,
        balances=balances,
        denomination=denomination,
    )
    return total_outstanding_debt + max_overpayment_fee


# TODO: this is duplicated within derived params as well. We may want to extract to
# an aggregated balances module
def get_total_outstanding_debt(
    balances: BalanceDefaultDict, denomination: str, precision: int = 2
) -> Decimal:
    return utils.sum_balances(
        balances=balances,
        addresses=lending_addresses.ALL_OUTSTANDING,
        denomination=denomination,
        decimal_places=precision,
    )


# TODO: this is duplicated within derived params as well. We may want to extract to
# an aggregated balances module
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


def get_outstanding_principal(balances: BalanceDefaultDict, denomination: str) -> Decimal:
    return utils.balance_at_coordinates(
        balances=balances,
        address=lending_addresses.PRINCIPAL,
        denomination=denomination,
    )


def handle_overpayment(
    vault: SmartContractVault,
    overpayment_amount: Decimal,
    denomination: str,
    balances: BalanceDefaultDict,
) -> list[Posting]:
    """Creates postings to handle standard overpayments to principal and accrued interest,
    updating any required trackers.

    :param vault: Vault object for the account receiving the overpayment
    :param overpayment_amount: the amount to go towards principal and accrued interest
    :param denomination: denomination of the repayment / loan being repaid
    :param balances: balances at the point of overpayment
    :return: the corresponding postings. Empty list if the overpayment amount isn't greater
    than 0, or if there is nothing to overpay
    """

    if overpayment_amount <= 0:
        return []

    postings: list[Posting] = []
    repayment_amount_remaining = overpayment_amount
    actual_outstanding_principal = get_outstanding_principal(balances, denomination)

    # the principal and interest features could be decoupled via an interface in the future
    if (overpayment_posting_amount := min(overpayment_amount, actual_outstanding_principal)) > 0:
        # The overpayment that has hit DEFAULT must be rebalanced to PRINCIPAL to reflect what
        # has been repaid, and OVERPAYMENT is used as a tracker

        postings += utils.create_postings(
            amount=overpayment_posting_amount,
            debit_account=vault.account_id,
            debit_address=DEFAULT_ADDRESS,
            credit_account=vault.account_id,
            credit_address=lending_addresses.PRINCIPAL,
            denomination=denomination,
        )
        postings += utils.create_postings(
            amount=overpayment_posting_amount,
            debit_account=vault.account_id,
            debit_address=OVERPAYMENT,
            credit_account=vault.account_id,
            credit_address=lending_addresses.INTERNAL_CONTRA,
            denomination=denomination,
        )
        postings += utils.create_postings(
            amount=overpayment_posting_amount,
            debit_account=vault.account_id,
            debit_address=OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
            credit_account=vault.account_id,
            credit_address=lending_addresses.INTERNAL_CONTRA,
            denomination=denomination,
        )
        repayment_amount_remaining -= overpayment_posting_amount

    postings += interest_application.repay_accrued_interest(
        vault=vault,
        repayment_amount=repayment_amount_remaining,
        balances=balances,
        denomination=denomination,
    )

    return postings


def track_emi_principal_excess(
    vault: SmartContractVault,
    interest_application_feature: lending_interfaces.InterestApplication,
    effective_datetime: datetime,
    previous_application_datetime: datetime,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """Creates posting instructions to track the emi principal excess as a result of overpayments.
    This function is intended for use as part of due amount calculation schedule.

    The emi principal excess comes from the reduced accruals as a result of an overpayment. These
    result in a lower than expected due interest, which in turn increases the portion of principal
    in subsequent emis. Tracking this means we can avoid reamortisation for non-overpayment reasons
    (e.g. variable rate change) from accidentally including the impact of overpayments that are
    meant to reduce the term.

    :param vault: vault object for the relevant account
    :param interest_application_feature: feature used by the account to apply interest
    :param balances: balances to base calculations on
    :param denomination: denomination of the relevant loan
    :return: list of posting instruction. May be empty (e.g. if no additional excess needs tracking)
    """

    if denomination is None:
        denomination = utils.get_parameter(vault=vault, name="denomination")
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=OVERPAYMENT_TRACKER_EFF_FETCHER_ID
        ).balances
    precision = interest_application_feature.get_application_precision(vault=vault)

    # expected interest includes emi and non-emi, so we must use total_rounded
    actual_interest_to_apply = interest_application_feature.get_interest_to_apply(
        vault=vault,
        effective_datetime=effective_datetime,
        previous_application_datetime=previous_application_datetime,
        denomination=denomination,
        application_precision=precision,
    ).total_rounded

    expected_interest_to_apply = utils.balance_at_coordinates(
        balances=balances,
        address=ACCRUED_EXPECTED_INTEREST,
        denomination=denomination,
        decimal_places=precision,
    )

    # this is the very definition of principal excess, as the actual interest accrued is
    # lower than the expected interest accrued, which means the emi principal portion is
    # higher than expected
    additional_emi_principal_excess = expected_interest_to_apply - actual_interest_to_apply

    postings = utils.create_postings(
        amount=additional_emi_principal_excess,
        debit_account=vault.account_id,
        debit_address=EMI_PRINCIPAL_EXCESS,
        credit_account=vault.account_id,
        credit_address=lending_addresses.INTERNAL_CONTRA,
        denomination=denomination,
    )
    if postings:
        return [
            CustomInstruction(
                postings=postings,
                override_all_restrictions=True,
                instruction_details={
                    "description": f"Increase principal excess due to {expected_interest_to_apply=}"
                    f" being larger than {actual_interest_to_apply=}"
                },
            )
        ]

    return []


def track_interest_on_expected_principal(
    vault: SmartContractVault,
    hook_arguments: Union[ScheduledEventHookArguments, SupervisorScheduledEventHookArguments],
    interest_rate_feature: lending_interfaces.InterestRate,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """Creates posting instructions to track interest on expected principal, which excludes the
    impact of overpayments. This function is intended for use as part of daily interest accrual.

    Expected interest helps determine the additional principal indirectly paid off after an
    overpayment due to subsequent accruals having a reduced principal, which in turn increases the
    portion of principal in the corresponding emi payments. This in turn avoids reamortisation for
    non-overpayment reasons (e.g. variable rate change) from accidentally including the impact of
    overpayments that are meant to reduce the term.
    :param vault: vault object for the account
    :param hook_arguments: hook arguments for the interest accrual event
    :param interest_rate_feature: feature used to determine the interest rate as of the
    hook_arguments' effective_datetime
    :param balances: Optional balances. Defaults to latest EOD balances before the hook_arguments'
    effective_datetime
    :param denomination: denomination to track in. Defaults to the `denomination` parameter
    :return: postings to track expected interest. Empty list if not required (e.g. 0 principal or 0
    interest rate)
    """

    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=EXPECTED_INTEREST_ACCRUAL_EOD_FETCHER_ID
        ).balances

    if denomination is None:
        denomination = str(utils.get_parameter(vault=vault, name="denomination"))

    precision = int(
        utils.get_parameter(vault=vault, name=interest_accrual_common.PARAM_ACCRUAL_PRECISION)
    )
    days_in_year: str = utils.get_parameter(
        vault=vault, name=interest_accrual_common.PARAM_DAYS_IN_YEAR, is_union=True
    )

    # the non-principal addresses are removed from principal during the lifecycle
    expected_principal = utils.sum_balances(
        balances=balances, denomination=denomination, addresses=EXPECTED_PRINCIPAL
    )
    yearly_rate = interest_rate_feature.get_annual_interest_rate(
        vault, hook_arguments.effective_datetime, balances=balances, denomination=denomination
    )
    accrual = interest_accrual_common.calculate_daily_accrual(
        effective_balance=expected_principal,
        effective_datetime=hook_arguments.effective_datetime,
        yearly_rate=yearly_rate,
        days_in_year=days_in_year,
        precision=precision,
    )

    if accrual and accrual.amount > 0:
        return [
            CustomInstruction(
                postings=utils.create_postings(
                    amount=accrual.amount,
                    debit_account=vault.account_id,
                    debit_address=ACCRUED_EXPECTED_INTEREST,
                    credit_account=vault.account_id,
                    credit_address=lending_addresses.INTERNAL_CONTRA,
                    denomination=denomination,
                ),
                instruction_details={
                    "description": f"Tracking expected interest at yearly rate {yearly_rate} on "
                    f"expected principal {expected_principal}"
                },
                override_all_restrictions=True,
            )
        ]

    return []


def reset_due_amount_calc_overpayment_trackers(
    vault: SmartContractVault,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """Resets accrued expected and overpayment since prev due amount calc tracker balances to 0.
    Intended for use in due amount calculation schedule.

    :param vault: vault object for the account
    :param balances: balances to base calculations on
    :param denomination: tracker denomination
    :return: custom instructions to reset tracker balances. May be empty list (e.g. no trackers to
    reset)
    """

    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=OVERPAYMENT_TRACKER_EFF_FETCHER_ID
        ).balances

    if denomination is None:
        denomination = str(utils.get_parameter(vault=vault, name="denomination"))

    reset_postings = utils.reset_tracker_balances(
        balances=balances,  # type: ignore
        account_id=vault.account_id,
        tracker_addresses=[
            ACCRUED_EXPECTED_INTEREST,
            OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
        ],
        contra_address=lending_addresses.INTERNAL_CONTRA,
        denomination=denomination,
        tside=Tside.ASSET,
    )

    if reset_postings:
        return [
            CustomInstruction(
                postings=reset_postings,
                instruction_details={"description": "Resetting overpayment trackers"},
                override_all_restrictions=True,
            )
        ]

    return []


def get_residual_cleanup_postings(
    balances: BalanceDefaultDict, account_id: str, denomination: str
) -> list[Posting]:
    return utils.reset_tracker_balances(
        balances=balances,  # type: ignore
        account_id=account_id,
        tracker_addresses=[
            ACCRUED_EXPECTED_INTEREST,
            EMI_PRINCIPAL_EXCESS,
            OVERPAYMENT,
            OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
        ],
        contra_address=lending_addresses.INTERNAL_CONTRA,
        denomination=denomination,
        tside=Tside.ASSET,
    )


def should_trigger_reamortisation(
    vault: SmartContractVault,
    period_start_datetime: datetime,
    period_end_datetime: datetime,
    elapsed_term: int,
) -> bool:
    """Indicates reamortisation is required if there has been an overpayment since the previous due
    amount calculation and the overpayment impact preference is to reduce emi.

    :param vault: vault object for the account
    :param period_start_datetime: start of period to evaluate reamortisation condition. Unused
    in this implementation
    :param period_end_datetime: start of period to evaluate reamortisation condition. Unused
    in this implementation
    :param elapsed_term: elapsed term on the loan. Unused in this implementation
    :return: boolean indicating whether reamortisation is required (True) or not (False).
    """
    balances = vault.get_balances_observation(
        fetcher_id=OVERPAYMENT_TRACKER_EFF_FETCHER_ID
    ).balances
    denomination: str = utils.get_parameter(vault=vault, name="denomination")

    overpayment_impact_preference_param = get_overpayment_preference_parameter(vault=vault)

    return (
        overpayment_impact_preference_param == REDUCE_EMI
        # The tracker balance has all overpayments since the prev due amount, which removes
        # the need for the start/end datetime
        and utils.balance_at_coordinates(
            balances=balances,
            address=OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
            denomination=denomination,
        )
        > 0
    )


def supervisor_should_trigger_reamortisation(
    loan_vault: SuperviseeContractVault,
    main_vault: SuperviseeContractVault,
    period_start_datetime: datetime,
    period_end_datetime: datetime,
    elapsed_term: Optional[int],
    balances: Optional[BalanceDefaultDict] = None,
) -> bool:
    """Indicates if reamortisation is required for supervisees if there has been
    an overpayment since the previous due amount calculation and the overpayment
    impact preference is to reduce emi.

    :param loan_vault: supervisee vault object for the account, used to fetch the denomination
    and balances if necessary
    :param main_vault: supervisee vault object, used to fetch the overpayment impact preference
    :param period_start_datetime: start of period to evaluate reamortisation condition. Unused
    in this implementation
    :param period_end_datetime: start of period to evaluate reamortisation condition. Unused
    in this implementation
    :param elapsed_term: elapsed term on the loan. Unused in this implementation
    :param balances: balances used to calculate the overpayment since the previous due amount
    calculation. Defaults to the latest balances if not passed in
    :return: boolean indicating whether reamortisation is required (True) or not (False).
    """

    if balances is None:
        balances_mapping = loan_vault.get_balances_timeseries()
        balances = utils.get_balance_default_dict_from_mapping(
            mapping=balances_mapping,
        )

    denomination: str = utils.get_parameter(vault=loan_vault, name="denomination")

    overpayment_impact_preference_param = get_overpayment_preference_parameter(vault=main_vault)

    return (
        overpayment_impact_preference_param == REDUCE_EMI
        # The tracker balance has all overpayments since the prev due amount, which removes
        # the need for the start/end datetime
        and utils.balance_at_coordinates(
            balances=balances,
            address=OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
            denomination=denomination,
        )
        > 0
    )


def calculate_principal_adjustment(
    vault: SmartContractVault,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    """
    Determines the adjustment as a result of overpayments that should be made to the principal,
    intended to be used inside the due_amount_calculation event
    :param vault: Vault object for the account, used to fetch the overpayment impact preference
    :param balances: Optional balances. Defaults to latest EOD balances'
    effective_datetime
    :param denomination: denomination to track in. Defaults to the `denomination` parameter
    """
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=EXPECTED_INTEREST_ACCRUAL_EOD_FETCHER_ID
        ).balances

    if denomination is None:
        denomination = utils.get_parameter(vault=vault, name="denomination")

    overpayment_preference = get_overpayment_preference_parameter(vault=vault)
    return (
        Decimal("0")
        if overpayment_preference == REDUCE_EMI
        else (
            utils.balance_at_coordinates(
                balances=balances,
                address=OVERPAYMENT,
                asset=DEFAULT_ASSET,
                denomination=denomination,
                phase=Phase.COMMITTED,
            )
            + utils.balance_at_coordinates(
                balances=balances,
                address=EMI_PRINCIPAL_EXCESS,
                asset=DEFAULT_ASSET,
                denomination=denomination,
                phase=Phase.COMMITTED,
            )
        )
    )


def supervisor_calculate_principal_adjustment(
    loan_vault: SuperviseeContractVault,
    main_vault: SuperviseeContractVault,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    """
    Determines the adjustment as a result of overpayments that should be made to the principal,
    intended to be used inside the supervisor_due_amount_calculation event. Gets parameters from
    both the loan_vault and main_vault. Functionally behaves like calculate_principal_adjustment
    :param loan_vault: supervisee vault object for the account, used to fetch balances
    :param main_vault: supervisee vault object, used to fetch the overpayment impact preference
    :param balances: Optional balances. Defaults to latest EOD balances' effective_datetime
    :param denomination: denomination to track in. Defaults to the `denomination` parameter
    """
    if balances is None:
        balances = loan_vault.get_balances_observation(
            fetcher_id=EXPECTED_INTEREST_ACCRUAL_EOD_FETCHER_ID
        ).balances

    if denomination is None:
        denomination = utils.get_parameter(vault=loan_vault, name="denomination")

    overpayment_preference = get_overpayment_preference_parameter(vault=main_vault)
    return (
        Decimal("0")
        if overpayment_preference == REDUCE_EMI
        else (
            utils.balance_at_coordinates(
                balances=balances,
                address=OVERPAYMENT,
                asset=DEFAULT_ASSET,
                denomination=denomination,
                phase=Phase.COMMITTED,
            )
            + utils.balance_at_coordinates(
                balances=balances,
                address=EMI_PRINCIPAL_EXCESS,
                asset=DEFAULT_ASSET,
                denomination=denomination,
                phase=Phase.COMMITTED,
            )
        )
    )


def get_overpayment_preference_parameter(vault: SmartContractVault) -> str:
    return str(
        utils.get_parameter(vault=vault, name=PARAM_OVERPAYMENT_IMPACT_PREFERENCE, is_union=True)
    )


def get_overpayment_fee_rate_parameter(vault: SmartContractVault) -> Decimal:
    overpayment_fee_rate: Decimal = utils.get_parameter(
        vault=vault, name=PARAM_OVERPAYMENT_FEE_RATE
    )
    return overpayment_fee_rate


def get_overpayment_fee_income_account_parameter(vault: SmartContractVault) -> str:
    overpayment_fee_income_account: str = utils.get_parameter(
        vault=vault, name=PARAM_OVERPAYMENT_FEE_INCOME_ACCOUNT
    )
    return overpayment_fee_income_account


OverpaymentFeature = lending_interfaces.Overpayment(
    handle_overpayment=handle_overpayment,
)

OverpaymentReamortisationCondition = lending_interfaces.ReamortisationCondition(
    should_trigger_reamortisation=should_trigger_reamortisation
)

SupervisorOverpaymentReamortisationCondition = lending_interfaces.SupervisorReamortisationCondition(
    should_trigger_reamortisation=supervisor_should_trigger_reamortisation
)

OverpaymentPrincipalAdjustment = lending_interfaces.PrincipalAdjustment(
    calculate_principal_adjustment=calculate_principal_adjustment
)

SupervisorOverpaymentPrincipalAdjustment = lending_interfaces.SupervisorPrincipalAdjustment(
    calculate_principal_adjustment=supervisor_calculate_principal_adjustment
)

OverpaymentResidualCleanupFeature = lending_interfaces.ResidualCleanup(
    get_residual_cleanup_postings=get_residual_cleanup_postings,
)


def get_early_repayment_overpayment_fee(
    vault: SmartContractVault,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    precision: int = 2,
) -> Decimal:
    """
    Get the early repayment overpayment fee amount. This is always the maximum overpayment fee.
    To be used as a get_early_repayment_fee_amount callable for an EarlyRepaymentFee interface.

    :param vault: vault object for the relevant account
    :param balances: balances to base calculations on
    :param denomination: denomination of the relevant loan
    :param precision: the number of decimal places to round to
    :return: the flat fee amount
    """
    balances = (
        vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances
        if balances is None
        else balances
    )
    denomination = (
        utils.get_parameter(vault=vault, name="denomination")
        if denomination is None
        else denomination
    )
    overpayment_fee_rate = get_overpayment_fee_rate_parameter(vault=vault)
    max_overpayment_fee = get_max_overpayment_fee(
        fee_rate=overpayment_fee_rate,
        balances=balances,
        denomination=denomination,
        precision=precision,
    )
    return max_overpayment_fee


def skip_charge_early_repayment_fee_for_overpayment(
    vault: SmartContractVault,
    account_id: str,
    amount_to_charge: Decimal,
    fee_name: str,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Skip the charge for the overpayment fee within an early repayment since this fee posting is
    already handled by the overpayment logic within post posting.  To be used as a
    charge_early_repayment_fee callable for an EarlyRepaymentFee interface.

    :param vault: only needed to satisfy the interface signature
    :param account_id: only needed to satisfy the interface signature
    :param amount_to_charge: only needed to satisfy the interface signature
    :param fee_name: only needed to satisfy the interface signature
    :param denomination: only needed to satisfy the interface signature
    :return: an empty list
    """
    return []


EarlyRepaymentOverpaymentFee = lending_interfaces.EarlyRepaymentFee(
    get_early_repayment_fee_amount=get_early_repayment_overpayment_fee,
    charge_early_repayment_fee=skip_charge_early_repayment_fee_for_overpayment,
    fee_name="Overpayment Fee",
)
