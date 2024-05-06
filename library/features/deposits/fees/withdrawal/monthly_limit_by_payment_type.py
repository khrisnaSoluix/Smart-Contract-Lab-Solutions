# standard lib
from datetime import datetime
from decimal import Decimal
from json import dumps as json_dumps

# inception lib
from inception_sdk.vault.contracts.types_extension import (
    ClientTransaction,
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    PostingInstruction,
    PostingInstructionBatch,
    StringShape,
    Level,
    Parameter,
    Vault,
)
import library.features.common.utils as utils
import library.features.common.transaction_utils as transaction_utils

PAYMENT_TYPE = "PAYMENT_TYPE"
INTERNAL_POSTING = "INTERNAL_POSTING"
MAXIMUM_BALANCE_PARAM = "maximum_balance"

parameters = [
    Parameter(
        name="maximum_monthly_payment_type_withdrawal_limit",
        level=Level.TEMPLATE,
        description="Fees required when the payment type hits the monthly limit",
        display_name="Monthly payment type withdrawal limit fees",
        shape=StringShape,
        default_value=json_dumps(
            {
                "ATM": {"fee": "0.50", "limit": "8"},
            }
        ),
    ),
]


def get_fees(
    vault: Vault,
    postings: PostingInstructionBatch,
    client_transactions: dict[tuple[str, str], ClientTransaction],
    effective_date: datetime,
    denomination: str,
) -> list[PostingInstruction]:
    """
    Check posting instruction details for PAYMENT_TYPE key and return any fees associated with that
    payment type. The fee is credited to the account defined by the payment_type_fee_income_account
    parameter.
    """
    maximum_monthly_payment_type_withdrawal_limit = utils.get_parameter(
        vault, "maximum_monthly_payment_type_withdrawal_limit", is_json=True
    )
    payment_type_fee_income_account = utils.get_parameter(vault, "payment_type_fee_income_account")

    start_of_monthly_window = effective_date.replace(day=1, hour=0, minute=0, second=0)

    posting_instructions = []
    total_fees_by_payment_type = {}
    for payment_type in maximum_monthly_payment_type_withdrawal_limit.keys():
        (
            previous_withdrawals,
            current_withdrawals,
        ) = transaction_utils.withdrawals_by_instruction_detail(
            denomination=denomination,
            postings=postings,
            client_transactions=client_transactions,
            cutoff_timestamp=start_of_monthly_window,
            instruction_detail_key=PAYMENT_TYPE,
            instruction_detail_value=payment_type,
        )
        current_payment_type_dict = maximum_monthly_payment_type_withdrawal_limit[payment_type]
        current_payment_type_fee = Decimal(current_payment_type_dict["fee"])
        current_payment_type_limit = Decimal(current_payment_type_dict["limit"])

        num_fees_to_incur = 0
        total_no_of_withdrawals = len(previous_withdrawals) + len(current_withdrawals)
        exceed_limit = total_no_of_withdrawals - current_payment_type_limit
        if exceed_limit > 0:
            num_fees_to_incur = min(exceed_limit, len(current_withdrawals))

        total_fee = num_fees_to_incur * current_payment_type_fee
        total_fees_by_payment_type.update({payment_type: total_fee})

    instruction_detail = "Total fees charged for limits on payment types: "
    instruction_detail += ",".join(
        [
            fee_by_type[0] + " " + str(fee_by_type[1]) + " " + denomination
            for fee_by_type in total_fees_by_payment_type.items()
        ]
    )
    total_fee = sum(total_fees_by_payment_type.values())
    if total_fee > 0:
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=total_fee,
                denomination=denomination,
                client_transaction_id=f"{INTERNAL_POSTING}_APPLY_PAYMENT_TYPE_"
                f"WITHDRAWAL_LIMIT_FEES_{vault.get_hook_execution_id()}",
                from_account_id=vault.account_id,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=payment_type_fee_income_account,
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                instruction_details={
                    "description": instruction_detail,
                    "event": "APPLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT_FEES",
                },
            )
        )

    return posting_instructions
