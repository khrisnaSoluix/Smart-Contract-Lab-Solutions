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
PARAM_PAYMENT_TYPE_THRESHOLD_FEE = "payment_type_threshold_fee"

parameters = [
    Parameter(
        name=PARAM_PAYMENT_TYPE_THRESHOLD_FEE,
        level=ParameterLevel.TEMPLATE,
        description="Fees required when the payment amount exceeds the threshold"
        " for the payment type",
        display_name="Payment Type Threshold Fee",
        shape=StringShape(),
        default_value=dumps(
            {
                "ATM": {"fee": "0.15", "threshold": "5000"},
            }
        ),
    ),
]


def apply_fees(
    vault: SmartContractVault, postings: utils.PostingInstructionListAlias, denomination: str
) -> list[CustomInstruction]:
    """
    Check posting instruction details for PAYMENT_TYPE key and return any fees associated with that
    payment type if the posting value breaches the associated limit. The fee is credited to the
    account defined by the payment_type_fee_income_account parameter.
    """
    payment_type_threshold_fee_param = utils.get_parameter(
        vault, PARAM_PAYMENT_TYPE_THRESHOLD_FEE, is_json=True
    )
    payment_type_fee_income_account = utils.get_parameter(vault, "payment_type_fee_income_account")

    posting_instructions: list[CustomInstruction] = []
    for posting in postings:
        current_payment_type = posting.instruction_details.get(PAYMENT_TYPE)
        if not current_payment_type or current_payment_type not in payment_type_threshold_fee_param:
            continue

        current_payment_type_dict = payment_type_threshold_fee_param[current_payment_type]
        payment_type_fee = Decimal(current_payment_type_dict["fee"])
        payment_type_threshold = Decimal(current_payment_type_dict["threshold"])

        posting_balances = posting.balances()
        available_balance_delta = utils.get_available_balance(
            balances=posting_balances, denomination=denomination
        )

        if -payment_type_threshold > available_balance_delta:
            instruction_details = utils.standard_instruction_details(
                description=(
                    f"payment fee on withdrawal more than {payment_type_threshold} for payment "
                    f"with type {current_payment_type}"
                ),
                event_type="APPLY_PAYMENT_TYPE_THRESHOLD_FEE",
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
