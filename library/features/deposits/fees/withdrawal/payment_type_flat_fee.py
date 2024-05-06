# standard lib
from decimal import Decimal
from json import dumps as json_dumps

# inception lib
from inception_sdk.vault.contracts.types_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    PostingInstruction,
    PostingInstructionBatch,
    StringShape,
    Level,
    Parameter,
    Phase,
    Vault,
)
import library.features.common.utils as utils

PAYMENT_TYPE = "PAYMENT_TYPE"
INTERNAL_POSTING = "INTERNAL_POSTING"
MAXIMUM_BALANCE_PARAM = "maximum_balance"

parameters = [
    Parameter(
        name="payment_type_flat_fee",
        level=Level.TEMPLATE,
        description="The flat fees to apply for a given payment type.",
        display_name="Payment type flat fees",
        shape=StringShape,
        default_value=json_dumps(
            {
                "ATM": "1",
            }
        ),
    ),
]


def get_fees(
    vault: Vault, postings: PostingInstructionBatch, denomination: str
) -> list[PostingInstruction]:
    """
    Check posting instruction details for PAYMENT_TYPE key and return any fees associated with that
    payment type. The fee is credited to the account defined by the payment_type_fee_income_account
    parameter.
    """
    payment_type_flat_fees = utils.get_parameter(vault, "payment_type_flat_fee", is_json=True)
    payment_type_fee_income_account = utils.get_parameter(vault, "payment_type_fee_income_account")

    posting_instructions = []
    for posting in postings:
        posting_balances = posting.balances()
        posting_withdrawal_amount = (
            posting_balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)].net
            + posting_balances[
                (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT)
            ].net
        )
        if posting_withdrawal_amount >= 0:
            continue

        current_payment_type = posting.instruction_details.get(PAYMENT_TYPE)
        if not current_payment_type or current_payment_type not in payment_type_flat_fees:
            continue

        payment_type_fee = Decimal(payment_type_flat_fees[current_payment_type])
        if payment_type_fee > 0:
            posting_instructions.extend(
                vault.make_internal_transfer_instructions(
                    amount=payment_type_fee,
                    denomination=denomination,
                    client_transaction_id=f"{INTERNAL_POSTING}_APPLY_PAYMENT_TYPE_FLAT_FEE_FOR"
                    f"_{current_payment_type}_{vault.get_hook_execution_id()}",
                    from_account_id=vault.account_id,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=payment_type_fee_income_account,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    instruction_details={
                        "description": f"payment fee applied for withdrawal using "
                        f"{current_payment_type}",
                        "payment_type": f"{current_payment_type}",
                        "event": "APPLY_PAYMENT_TYPE_FLAT_FEE",
                    },
                )
            )

    return posting_instructions
