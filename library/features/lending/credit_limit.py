# standard lib
from decimal import Decimal
from typing import Optional

# inception lib
from inception_sdk.vault.contracts.supervisor.types_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    RejectedReason,
    Rejected,
    Level,
    Parameter,
    Phase,
    PostingInstruction,
    UpdatePermission,
)
import library.features.common.utils as utils
import library.features.common.supervisor_utils as supervisor_utils
import library.features.lending.addresses as addresses

CREDIT_LIMIT_PARAM = "credit_limit"

parameters = [
    Parameter(
        name=CREDIT_LIMIT_PARAM,
        level=Level.INSTANCE,
        description="Maximum credit limit available to the customer",
        display_name="Customer Credit Limit",
        shape=utils.LimitHundredthsShape,
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=Decimal("1000"),
    ),
]


def validate(
    loc_vault,
    loans: list,
    posting: PostingInstruction,
    observation_fetcher_id: str,
    denomination: Optional[str] = None,
    non_repayable_addresses: Optional[list[str]] = None,
):
    """
    Rejects postings if resulting credit usage exceeds customer's credit limit. For use inside
    supervisor pre-posting hook only. Assumes the posting has already been confirmed to be a
    an outbound hard settlement representing a drawdown request.

    :param loc_vault: the Line of Credit Vault object with the credit limit parameters
    :param loans: the Drawdown loan vault objects with the principal amounts
    :param posting: the posting to validate.
    :param observation_fetcher_id: the fetcher id used to retrieve balances to validate against
    :param denomination: the line of credit's denomination
    :param non_repayable_addresses: an optional list of non repayable addresses that use
    loc_vault's INTERNAL_CONTRA. This should be determined by the features at use
    :raises Rejected: raised if the posting amount would cause the credit limit to be exceeded
    """

    credit_limit = utils.get_parameter(loc_vault, CREDIT_LIMIT_PARAM)

    associated_original_principal = sum(
        Decimal(utils.get_parameter(loan_vault, "principal")) for loan_vault in loans
    )
    associated_outstanding_principal = supervisor_utils.sum_balances_across_supervisees(
        loans,
        utils.get_parameter(loc_vault, "denomination"),
        addresses=[addresses.PRINCIPAL, addresses.PRINCIPAL_DUE, addresses.PRINCIPAL_OVERDUE],
        observation_fetcher_id=observation_fetcher_id,
    )

    used_credit_limit = associated_outstanding_principal

    # There may be drawdown requests that have not yet had corresponding loans associated to the
    # plan. We must account for these to avoid authorising too many requests.
    # LOC default net = original principals - repayments
    # We expect original principals = associated principals, but if if a loan was not yet
    # associated its principle would not show in associated principals. This would result in a
    # delta between the LHS and RHS of equation 1. corresponding to reserved credit limit without
    # a corresponding loan. This must be added to the used limit

    loc_default_net = (
        loc_vault.get_balances_observation(fetcher_id=observation_fetcher_id)
        .balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED]
        .net
    )

    # Summing internal contra and non repayable balances leaves us with repayments for
    # associated loans because contra is temporarily used for repayments until loans are closed
    # Note: we can't just look at credits to determine repayments as we must know the repayments
    # for the associated loans specifically
    associated_repayments = supervisor_utils.sum_balances_across_supervisees(
        loans,
        utils.get_parameter(loc_vault, "denomination"),
        addresses=(non_repayable_addresses or []) + [addresses.INTERNAL_CONTRA],
        observation_fetcher_id=observation_fetcher_id,
    )

    delta = loc_default_net - associated_original_principal + associated_repayments

    used_credit_limit += delta

    remaining_credit_limit = credit_limit - used_credit_limit

    if posting.amount > remaining_credit_limit:
        raise Rejected(
            f"Attempted drawdown {posting.amount} {denomination} exceeds the remaining limit of "
            f"{remaining_credit_limit} {denomination}, based on outstanding principal",
            reason_code=RejectedReason.AGAINST_TNC,
        )
