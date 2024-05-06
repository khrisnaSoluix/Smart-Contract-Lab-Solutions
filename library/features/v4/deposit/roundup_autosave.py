# CBF: Round Up Autosave

# standard libs
from decimal import Decimal
from json import dumps
from typing import Optional

# features
import library.features.common.common_parameters as common_parameters
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import (
    AccountIdShape,
    BalanceDefaultDict,
    CustomInstruction,
    NumberShape,
    OptionalShape,
    OptionalValue,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    Phase,
    Posting,
    StringShape,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

TRANSACTION_TYPE = "TRANSACTION_TYPE"
DEFAULT_TRANSACTION_TYPE = "PURCHASE"

# Parameters
PARAM_ROUNDUP_AUTOSAVE_ROUNDING_AMOUNT = "roundup_autosave_rounding_amount"
PARAM_ROUNDUP_AUTOSAVE_ACCOUNT = "roundup_autosave_account"
PARAM_ROUNDUP_AUTOSAVE_TRANSACTION_TYPES = "roundup_autosave_transaction_types"
PARAM_ROUNDUP_AUTOSAVE_ACTIVE = "roundup_autosave_active"

parameters = [
    # Template params
    Parameter(
        name=PARAM_ROUNDUP_AUTOSAVE_ROUNDING_AMOUNT,
        level=ParameterLevel.TEMPLATE,
        description="For any given spend with the primary denomination, this is the figure to "
        "round up to: the nearest multiple higher than the transaction amount. "
        "Only used if autosave_savings_account is defined "
        "and if the transaction type is eligible (see Autosave Transaction Types)",
        display_name="Autosave Rounding Amount",
        shape=OptionalShape(shape=NumberShape(min_value=0, step=Decimal("0.01"))),
        default_value=OptionalValue(Decimal("1.00")),
    ),
    Parameter(
        name=PARAM_ROUNDUP_AUTOSAVE_TRANSACTION_TYPES,
        level=ParameterLevel.TEMPLATE,
        description="The list of transaction types eligible for autosave. "
        "Expects a JSON-encoded list",
        display_name="Autosave Transaction Types",
        shape=OptionalShape(shape=StringShape()),
        default_value=OptionalValue(dumps([DEFAULT_TRANSACTION_TYPE])),
    ),
    # Instance params
    Parameter(
        name=PARAM_ROUNDUP_AUTOSAVE_ACCOUNT,
        level=ParameterLevel.INSTANCE,
        description="The account credited with Round-up Autosave amounts",
        display_name="Autosave Account",
        shape=OptionalShape(shape=AccountIdShape()),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
        default_value=OptionalValue(""),
    ),
    Parameter(
        name=PARAM_ROUNDUP_AUTOSAVE_ACTIVE,
        level=ParameterLevel.INSTANCE,
        description="Switch that controls if the Round-up autosave feature is active or disabled.",
        display_name="Round-up Autosave Active",
        shape=common_parameters.BooleanShape,
        update_permission=ParameterUpdatePermission.USER_EDITABLE,
        default_value=common_parameters.BooleanValueTrue,
    ),
]


def apply(
    *,
    vault: SmartContractVault,
    postings: utils.PostingInstructionListAlias,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
) -> list[CustomInstruction]:
    """
    Creates the postings instructions required to perform auto save for the committed amounts.
    The feature requires the autosave_rounding_amount and autosave_savings_account to be set
    :param vault: The vault object containing parameters, etc.
    :param postings: posting instructions
    :param denomination: the default denomination of the account
    :param balances: Balances used to determine the available balance
    :return: List of CustomInstruction with postings to perform auto save transaction
    """

    # if roundup_autosave_flag is False the feature is disabled
    if not utils.str_to_bool(
        utils.get_parameter(vault=vault, name=PARAM_ROUNDUP_AUTOSAVE_ACTIVE, is_union=True)
    ):
        return []

    # roundup_autosave_transaction_types is not validate as it defaults to PURCHASE.
    if not utils.are_optional_parameters_set(
        vault=vault,
        parameters=[PARAM_ROUNDUP_AUTOSAVE_ROUNDING_AMOUNT, PARAM_ROUNDUP_AUTOSAVE_ACCOUNT],
    ):
        return []

    if denomination is None:
        denomination = utils.get_parameter(vault=vault, name="denomination")

    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances

    available_balance: Decimal = utils.get_available_balance(
        balances=balances, denomination=denomination
    )
    if available_balance <= 0:
        return []

    autosave_rounding_amount: Decimal = utils.get_parameter(
        name=PARAM_ROUNDUP_AUTOSAVE_ROUNDING_AMOUNT, vault=vault, is_optional=True
    )
    autosave_savings_account: str = utils.get_parameter(
        name=PARAM_ROUNDUP_AUTOSAVE_ACCOUNT, vault=vault, is_optional=True
    )
    autosave_transaction_types: list[str] = utils.get_parameter(
        name=PARAM_ROUNDUP_AUTOSAVE_TRANSACTION_TYPES,
        vault=vault,
        is_json=True,
        is_optional=True,
        default_value=[DEFAULT_TRANSACTION_TYPE],
    )

    autosave_amount = Decimal("0")

    instruction_description = ""
    posting_result: list[Posting] = []
    for posting in postings:
        posting_transaction_type = posting.instruction_details.get(TRANSACTION_TYPE)
        if posting_transaction_type not in autosave_transaction_types:
            continue

        posting_balance = utils.balance_at_coordinates(
            balances=posting.balances(),
            denomination=denomination,
            phase=Phase.COMMITTED,
        )

        # Posting balance should be negative to indicate its withdrawal
        if posting_balance >= 0:
            continue
        posting_balance = abs(posting_balance)
        remainder = posting_balance % autosave_rounding_amount
        if remainder > 0:
            debit_amount = autosave_rounding_amount - remainder

            # Make sure there is enough balance in the account to debit
            if autosave_amount + debit_amount <= available_balance:
                autosave_amount += debit_amount
                posting_result.extend(
                    utils.create_postings(
                        amount=debit_amount,
                        denomination=denomination,
                        debit_account=vault.account_id,
                        credit_account=autosave_savings_account,
                    )
                )
                instruction_description += (
                    f"Roundup Autosave: {denomination} {debit_amount} "
                    f"using round up to {denomination} {autosave_rounding_amount} for transfer of "
                    f"{denomination} {posting_balance}\n "
                )

    if posting_result:
        return [
            CustomInstruction(
                postings=posting_result,
                instruction_details={
                    "description": instruction_description,
                    "event": "ROUNDUP_AUTOSAVE",
                },
                override_all_restrictions=True,
            )
        ]

    return []
