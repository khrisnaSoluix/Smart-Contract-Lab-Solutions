# standard libs
from decimal import Decimal
from typing import Optional, Union

# features
import library.features.common.fetchers as fetchers
import library.features.v4.common.supervisor_utils as supervisor_utils
import library.features.v4.common.utils as utils
import library.features.v4.lending.lending_addresses as addresses

# contracts api
from contracts_api import (
    BalanceDefaultDict,
    BalancesObservationFetcher,
    DefinedDateTime,
    NumberShape,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    Rejection,
    RejectionReason,
    UnionItem,
    UnionItemValue,
    UnionShape,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import (
    SmartContractVault,
    SuperviseeContractVault,
)

# Fetchers
LIVE_BALANCES_BOF_ID = "live_balances_bof"
LIVE_BALANCES_BOF = BalancesObservationFetcher(
    fetcher_id=LIVE_BALANCES_BOF_ID,
    at=DefinedDateTime.LIVE,
)
data_fetchers = [LIVE_BALANCES_BOF]

PARAM_CREDIT_LIMIT = "credit_limit"
PARAM_CREDIT_LIMIT_APPLICABLE_PRINCIPAL = "credit_limit_applicable_principal"
PARAM_DENOMINATION = "denomination"
CREDIT_LIMIT_ORIGINAL = "original"
CREDIT_LIMIT_OUTSTANDING = "outstanding"

parameters = [
    Parameter(
        name=PARAM_CREDIT_LIMIT,
        level=ParameterLevel.INSTANCE,
        description="Maximum credit limit available to the customer",
        display_name="Customer Credit Limit",
        shape=NumberShape(min_value=Decimal("0")),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
        default_value=Decimal("1000"),
    ),
    Parameter(
        name=PARAM_CREDIT_LIMIT_APPLICABLE_PRINCIPAL,
        shape=UnionShape(
            items=[
                UnionItem(key=CREDIT_LIMIT_ORIGINAL, display_name="Original"),
                UnionItem(key=CREDIT_LIMIT_OUTSTANDING, display_name="Outstanding"),
            ]
        ),
        level=ParameterLevel.TEMPLATE,
        description="Defines whether the available credit limit is calculated using the original"
        " or outstanding principal for all open loans.",
        display_name="Available Credit Limit Definition",
        default_value=UnionItemValue(key=CREDIT_LIMIT_OUTSTANDING),
    ),
]


def validate(
    main_vault: SuperviseeContractVault,
    loans: list[SuperviseeContractVault],
    posting_instruction: utils.PostingInstructionTypeAlias,
    non_repayable_addresses: Optional[list[str]] = None,
) -> Optional[Rejection]:
    main_vault_balances = main_vault.get_balances_observation(
        fetcher_id=LIVE_BALANCES_BOF_ID
    ).balances
    loan_balances = supervisor_utils.get_balance_default_dicts_for_supervisees(
        supervisees=loans, fetcher_id=LIVE_BALANCES_BOF_ID
    )
    denomination = _get_denomination_parameter(vault=main_vault)

    associated_original_principal = calculate_associated_original_principal(loans=loans)
    unassociated_principal = calculate_unassociated_principal(
        main_vault_balances=main_vault_balances,
        loan_balances=loan_balances,
        denomination=denomination,
        associated_original_principal=associated_original_principal,
        non_repayable_addresses=non_repayable_addresses,
    )

    credit_limit = _get_credit_limit_parameter(vault=main_vault)
    applicable_principal = _get_applicable_principal_parameter(vault=main_vault)
    available_credit_limit = calculate_available_credit_limit(
        loan_balances=loan_balances,
        credit_limit=credit_limit,
        applicable_principal=applicable_principal,
        denomination=denomination,
        associated_original_principal=associated_original_principal,
        unassociated_principal=unassociated_principal,
    )

    posting_amount = utils.get_available_balance(
        balances=posting_instruction.balances(), denomination=denomination
    )
    if posting_amount > available_credit_limit:
        return Rejection(
            message=f"Incoming posting of {posting_amount} exceeds available credit limit "
            f"of {available_credit_limit}",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None


def calculate_associated_original_principal(loans: list[SuperviseeContractVault]) -> Decimal:
    associated_original_principal = sum(
        Decimal(utils.get_parameter(loan_vault, "principal")) for loan_vault in loans
    )
    return Decimal(associated_original_principal)


def calculate_unassociated_principal(
    main_vault_balances: BalanceDefaultDict,
    loan_balances: list[BalanceDefaultDict],
    denomination: str,
    associated_original_principal: Decimal,
    non_repayable_addresses: Optional[list[str]] = None,
) -> Decimal:

    # Drawdown requests can be determined from the default balance as:
    # default balance = drawdown requests - repayments
    # and drawdown_requests = associated original principal + unassociated original principal
    # Rearranging yields:
    # unassociated original principal = default balance - associated original principal + repayments

    # Here we can use internal contra to implicitly get the repayment amounts for the associated
    # loans because contra is temporarily used for repayments until loans are closed
    # Note: we can't just look at credits to determine repayments as we must know the repayments
    # for the associated loans specifically
    non_repayable_addresses = non_repayable_addresses or []
    if addresses.INTERNAL_CONTRA not in non_repayable_addresses:
        non_repayable_addresses.append(addresses.INTERNAL_CONTRA)

    associated_repayments = supervisor_utils.sum_balances_across_supervisees(
        balances=loan_balances,
        denomination=denomination,
        addresses=non_repayable_addresses,
    )

    main_vault_default_net = utils.balance_at_coordinates(
        balances=main_vault_balances, denomination=denomination
    )

    unassociated_original_principal = (
        main_vault_default_net - associated_original_principal + associated_repayments
    )
    return unassociated_original_principal


def calculate_available_credit_limit(
    loan_balances: list[BalanceDefaultDict],
    credit_limit: Decimal,
    applicable_principal: str,
    denomination: str,
    associated_original_principal: Decimal,
    unassociated_principal: Decimal,
) -> Decimal:

    # Remaining credit limit is defined as:
    # credit limit - associated principal - unassociated original principal, where:
    # - "Associated principal" is the sum total of associated loans' original/outstanding principal
    #   based on the value of CREDIT_LIMIT_APPLICABLE_PRINCIPAL_PARAM.
    # - "Unassociated principal" is the sum total of drawdown requests that aren't yet materialised
    #   as a loan (e.g. due to delays between authorising the drawdown and opening + association
    #   the drawdown loan account).

    available_credit_limit = credit_limit - unassociated_principal
    if applicable_principal == CREDIT_LIMIT_ORIGINAL:
        available_credit_limit -= associated_original_principal
    else:
        associated_outstanding_principal = supervisor_utils.sum_balances_across_supervisees(
            balances=loan_balances,
            denomination=denomination,
            addresses=addresses.ALL_PRINCIPAL,
        )
        available_credit_limit -= associated_outstanding_principal

    return available_credit_limit


# parameter getters
def _get_denomination_parameter(vault: Union[SmartContractVault, SuperviseeContractVault]) -> str:
    denomination: str = utils.get_parameter(vault=vault, name=PARAM_DENOMINATION)
    return denomination


def _get_credit_limit_parameter(vault: SuperviseeContractVault) -> Decimal:
    credit_limit: Decimal = utils.get_parameter(vault=vault, name=PARAM_CREDIT_LIMIT)
    return credit_limit


def _get_applicable_principal_parameter(vault: SuperviseeContractVault) -> str:
    applicable_principal: str = utils.get_parameter(
        vault=vault,
        name=PARAM_CREDIT_LIMIT_APPLICABLE_PRINCIPAL,
        is_union=True,
    )
    return applicable_principal


def validate_credit_limit_parameter_change(
    vault: Union[SmartContractVault, SuperviseeContractVault],
    proposed_credit_limit: Decimal,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    principal_addresses: list[str] = addresses.ALL_PRINCIPAL,
) -> Optional[Rejection]:
    """
    Returns a rejection if the proposed credit limit is below the total
    outstanding principal

    :param vault: The vault object containing the live balances to use in the validation
    :param proposed_credit_limit: The new proposed credit limit
    :param balances: The balances used to determine the total outstanding principal
    :param denomination: The denomination of the account
    :param principal_addresses: The addresses that contain all the outstanding principal
    :return: A rejection if the proposed credit limit is invalid, otherwise None
    """
    if not balances:
        balances = vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances

    if not denomination:
        denomination = _get_denomination_parameter(vault=vault)

    total_outstanding_principal = utils.sum_balances(
        balances=balances,
        denomination=denomination,
        addresses=principal_addresses,
    )

    if proposed_credit_limit < total_outstanding_principal:
        return Rejection(
            message=f"Cannot set proposed credit limit {proposed_credit_limit} "
            "to a value below the total outstanding debt of "
            f"{total_outstanding_principal}",
            reason_code=RejectionReason.AGAINST_TNC,
        )

    return None
