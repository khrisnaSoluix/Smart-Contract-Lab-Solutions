# CBF: Overdraft Coverage

# standard libs
from datetime import datetime
from decimal import Decimal
from json import dumps
from typing import Optional

# features
import library.features.common.common_parameters as common_parameters
import library.features.common.fetchers as fetchers
import library.features.v4.common.transaction_type_utils as transaction_type_utils
import library.features.v4.common.utils as utils
import library.features.v4.deposit.transaction_limits.overdraft.overdraft_limit as overdraft_limit

# contracts api
from contracts_api import (
    BalanceDefaultDict,
    OptionalShape,
    OptionalValue,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    Rejection,
    RejectionReason,
    StringShape,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

PARAM_OVERDRAFT_OPT_IN = "overdraft_coverage_opted_in"
PARAM_EXCLUDED_OVERDRAFT_COVERAGE_LIST = "excluded_overdraft_coverage_transaction_types"
PARAM_ARRANGED_OVERDRAFT_AMOUNT = overdraft_limit.PARAM_ARRANGED_OVERDRAFT_AMOUNT
PARAM_UNARRANGED_OVERDRAFT_AMOUNT = overdraft_limit.PARAM_UNARRANGED_OVERDRAFT_AMOUNT

parameters = [
    Parameter(
        name=PARAM_OVERDRAFT_OPT_IN,
        level=ParameterLevel.INSTANCE,
        description="Defines whether the customer has opted-in to allow the excluded transactions "
        "to utilise the overdraft limit.",
        display_name="Overdraft Coverage Enabled",
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
        shape=OptionalShape(shape=common_parameters.BooleanShape),
        default_value=OptionalValue(common_parameters.BooleanValueFalse),
    ),
    Parameter(
        name=PARAM_EXCLUDED_OVERDRAFT_COVERAGE_LIST,
        level=ParameterLevel.TEMPLATE,
        description="Transaction types specifically excluded from utilising the overdraft limit. "
        "Unless specifically opted-in to do so. "
        "Expects a string representation of a JSON list.",
        display_name="Overdraft Coverage List",
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
        shape=StringShape(),
        default_value=dumps([]),
    ),
    *overdraft_limit.parameters,
]


def validate(
    *,
    vault: SmartContractVault,
    postings: utils.PostingInstructionListAlias,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
    effective_datetime: Optional[datetime] = None,
) -> Optional[Rejection]:
    """
    Return Rejection if a transaction will cause the account to go into overdraft. If the customer
    has opted-in for overdraft coverage then all transaction types are allowed to utilise the
    overdraft funds and thus the entire list of postings is evaluated. If the customer has not opted
    for overdraft coverage then each posting is evaluated individually, in the order they're
    provided.

    :param vault: Vault object for the account whose overdraft limit is being validated
    :param postings: posting instructions being processed
    :param denomination: denomination
    :param balances: account balances available, if not provided will be retrieved
    using the LIVE_BALANCES_BOF_ID fetcher id
    :param effective_datetime: the time at which the parameters should be fetched. If not
    specified the latest value is retrieved.
    :return: rejection if overdraft criteria not satisfied
    """
    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)

    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances

    if _get_coverage_opt_in(vault=vault, effective_datetime=effective_datetime):
        # Opted into coverage, therefore all transaction types are allowed to utilise the overdraft
        # limit.
        return overdraft_limit.validate(
            vault=vault, postings=postings, denomination=denomination, balances=balances
        )

    available_balance = utils.get_available_balance(balances=balances, denomination=denomination)
    excluded_transaction_types = _get_excluded_coverage_list(
        vault=vault, effective_datetime=effective_datetime
    )
    total_overdraft_limit = overdraft_limit.get_arranged_overdraft_amount(
        vault=vault
    ) + overdraft_limit.get_unarranged_overdraft_amount(vault=vault)

    total_available_balance = available_balance + total_overdraft_limit
    available_balance_for_excluded_transaction_types = available_balance

    for posting in postings:
        balance_impact = utils.get_available_balance(
            balances=posting.balances(), denomination=denomination
        )
        total_available_balance += balance_impact
        available_balance_for_excluded_transaction_types += balance_impact

        is_excluded_transaction_type = transaction_type_utils.match_transaction_type(
            posting_instruction=posting, values=excluded_transaction_types
        )

        if (
            is_excluded_transaction_type
            and available_balance_for_excluded_transaction_types < Decimal("0")
        ) or (not is_excluded_transaction_type and total_available_balance < Decimal("0")):
            posting_type = posting.instruction_details.get("type", "")
            rejection_message = (
                f"{posting_type=} exceeds the total available balance of the account."
            )
            if is_excluded_transaction_type:
                rejection_message += (
                    " This transaction is an excluded transaction type which requires "
                    "overdraft coverage opt-in to utilise the overdraft limit."
                )

            return Rejection(
                message=rejection_message,
                reason_code=RejectionReason.INSUFFICIENT_FUNDS,
            )

    return None


def _get_coverage_opt_in(
    *, vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> bool:
    return utils.get_parameter(
        vault=vault,
        name=PARAM_OVERDRAFT_OPT_IN,
        at_datetime=effective_datetime,
        is_boolean=True,
        is_optional=True,
    )


def _get_excluded_coverage_list(
    *, vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> list[str]:
    return utils.get_parameter(
        vault=vault,
        name=PARAM_EXCLUDED_OVERDRAFT_COVERAGE_LIST,
        at_datetime=effective_datetime,
        is_json=True,
    )


get_arranged_overdraft_amount = overdraft_limit.get_arranged_overdraft_amount
get_unarranged_overdraft_amount = overdraft_limit.get_unarranged_overdraft_amount

OverdraftCoverageAvailableBalance = overdraft_limit.OverdraftLimitAvailableBalance
