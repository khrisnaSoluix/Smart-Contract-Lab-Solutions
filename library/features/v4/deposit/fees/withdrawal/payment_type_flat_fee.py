# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.

# standard libs
from decimal import Decimal
from json import dumps

# features
import library.features.v4.common.fees as fees
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import CustomInstruction, Parameter, ParameterLevel, StringShape

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# payment
PAYMENT_TYPE = "PAYMENT_TYPE"

# Parameters
PARAM_PAYMENT_TYPE_FLAT_FEE = "payment_type_flat_fee"

parameters = [
    Parameter(
        name=PARAM_PAYMENT_TYPE_FLAT_FEE,
        level=ParameterLevel.TEMPLATE,
        description="The flat fees to apply for a given payment type.",
        display_name="Payment Type Flat Fees",
        shape=StringShape(),
        default_value=dumps(
            {
                "ATM": "1",
            }
        ),
    ),
]


def apply_fees(
    vault: SmartContractVault, postings: utils.PostingInstructionListAlias, denomination: str
) -> list[CustomInstruction]:
    """
    Check posting instruction details for PAYMENT_TYPE key and return any fees associated with that
    payment type. The fee is credited to the account defined by the payment_type_fee_income_account
    parameter.
    """
    payment_type_flat_fees = utils.get_parameter(vault, PARAM_PAYMENT_TYPE_FLAT_FEE, is_json=True)
    payment_type_fee_income_account = utils.get_parameter(vault, "payment_type_fee_income_account")

    posting_instructions: list[CustomInstruction] = []
    for posting in postings:
        current_payment_type = posting.instruction_details.get(PAYMENT_TYPE)
        if not current_payment_type or current_payment_type not in payment_type_flat_fees:
            continue

        posting_balances = posting.balances()
        posting_withdrawal_amount = utils.get_available_balance(
            balances=posting_balances, denomination=denomination
        )
        if posting_withdrawal_amount >= 0:
            continue

        payment_type_fee = Decimal(payment_type_flat_fees[current_payment_type])
        if payment_type_fee > 0:
            instruction_details = utils.standard_instruction_details(
                description=(f"payment fee applied for withdrawal using {current_payment_type}"),
                event_type="APPLY_PAYMENT_TYPE_FLAT_FEE",
                gl_impacted=True,
            )
            instruction_details["payment_type"] = current_payment_type
            posting_instructions.extend(
                fees.fee_custom_instruction(
                    customer_account_id=vault.account_id,
                    denomination=denomination,
                    amount=payment_type_fee,
                    internal_account=payment_type_fee_income_account,
                    instruction_details=instruction_details,
                )
            )

    return posting_instructions
