from decimal import Decimal

# inception library
from inception_sdk.vault.contracts.types_extension import (
    Vault,
    Parameter,
    NumberShape,
    Level,
    NumberKind,
    UpdatePermission,
    AccountIdShape,
    PostingInstruction,
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
)
import library.features.common.utils as utils

PRINCIPAL = "PRINCIPAL"

parameters = [
    Parameter(
        name="principal",
        shape=NumberShape(kind=NumberKind.MONEY, min_value=Decimal("0")),
        level=Level.INSTANCE,
        description="The agreed amount the customer will borrow from the bank.",
        display_name="Loan principal",
        default_value=Decimal("1000"),
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name="deposit_account",
        shape=AccountIdShape,
        level=Level.INSTANCE,
        description="The account to which the principal borrowed amount will be transferred.",
        display_name="Deposit account",
        default_value="00000000-0000-0000-0000-000000000000",
        update_permission=UpdatePermission.FIXED,
    ),
]


def get_posting_instructions(
    vault: Vault, denomination: str, principal_address: str = PRINCIPAL
) -> list[PostingInstruction]:
    principal = utils.get_parameter(vault, name="principal")
    deposit_account_id = utils.get_parameter(vault, name="deposit_account")

    posting_instructions = vault.make_internal_transfer_instructions(
        amount=principal,
        denomination=denomination,
        client_transaction_id=vault.get_hook_execution_id() + "_PRINCIPAL_DISBURSEMENT",
        from_account_id=vault.account_id,
        from_account_address=principal_address,
        to_account_id=deposit_account_id,
        to_account_address=DEFAULT_ADDRESS,
        instruction_details={
            "description": f"Principal disbursement of {principal}",
            "event": "PRINCIPAL_PAYMENT",
        },
        asset=DEFAULT_ASSET,
    )

    return posting_instructions
