# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.

# standard libs
from datetime import datetime
from decimal import Decimal
from json import dumps
from typing import Optional

# features
import library.features.v4.common.client_transaction_utils as client_transaction_utils
import library.features.v4.common.fees as fees
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import (
    ClientTransaction,
    CustomInstruction,
    Parameter,
    ParameterLevel,
    StringShape,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# payment
PAYMENT_TYPE = "PAYMENT_TYPE"

# Parameters
PARAM_MAXIMUM_MONTHLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT = (
    "maximum_monthly_payment_type_withdrawal_limit"
)

parameters = [
    Parameter(
        name=PARAM_MAXIMUM_MONTHLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT,
        level=ParameterLevel.TEMPLATE,
        description="Fees required when the number of payments exceeds the monthly limit for that "
        "payment type.",
        display_name="Monthly Payment Type Withdrawal Limit Fees",
        shape=StringShape(),
        default_value=dumps(
            {
                "ATM": {"fee": "0.50", "limit": "8"},
            }
        ),
    ),
]

data_fetchers = [
    fetchers.MONTH_TO_EFFECTIVE_POSTINGS_FETCHER,
]


def apply_fees(
    vault: SmartContractVault,
    effective_datetime: datetime,
    denomination: str,
    updated_client_transactions: dict[str, ClientTransaction],
    historic_client_transactions: Optional[dict[str, ClientTransaction]] = None,
) -> list[CustomInstruction]:
    """
    From the client transactions, check posting instruction details for PAYMENT_TYPE key and return
    any fees associated with that payment type. The fee is credited to the internal account defined
    by the payment_type_fee_income_account parameter.

    :param vault: The vault object containing parameters, balances, etc.
    :param effective_datetime: The effective datetime for fee application.
    :param denomination: The denomination of the fee.
    :param updated_client_transactions: new or updated client transactions that may count towards
    the limit. Typically from PostPostingHookArguments.client_transactions.
    :param historic_client_transactions: Historic client transactions that may count towards the
    limit. Should cover the period from start-of-month to effective datetime. If not provided,
    fetched using MONTH_TO_EFFECTIVE_POSTINGS_FETCHER_ID fetcher.

    :return: Returns the Custom Instruction for charging the fee.
    """

    if historic_client_transactions is None:
        historic_client_transactions = vault.get_client_transactions(
            fetcher_id=fetchers.MONTH_TO_EFFECTIVE_POSTINGS_FETCHER_ID
        )

    maximum_monthly_payment_type_withdrawal_limit: dict[str, dict[str, str]] = utils.get_parameter(
        vault, PARAM_MAXIMUM_MONTHLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT, is_json=True
    )
    payment_type_fee_income_account = utils.get_parameter(vault, "payment_type_fee_income_account")

    start_of_monthly_window = effective_datetime.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    posting_instructions: list[CustomInstruction] = []
    total_fees_by_payment_type: dict[str, Decimal] = {}
    for payment_type, payment_type_config in maximum_monthly_payment_type_withdrawal_limit.items():
        # If payment_type_config invalid, the assumption is no fee. Invalid defined as:
        # e.g. fee or limit keys don't exist; fee is zero or negative; limit is negative.
        payment_type_fee = Decimal(payment_type_config.get("fee", 0))
        payment_type_limit = int(payment_type_config.get("limit", -1))
        if payment_type_fee <= 0 or payment_type_limit < 0:
            continue

        historic_withdrawals = client_transaction_utils.extract_debits_by_instruction_details_key(
            denomination=denomination,
            client_transactions=historic_client_transactions,
            client_transaction_ids_to_ignore=[],
            cutoff_datetime=start_of_monthly_window,
            key=PAYMENT_TYPE,
            value=payment_type,
        )

        new_withdrawals = client_transaction_utils.extract_debits_by_instruction_details_key(
            denomination=denomination,
            client_transactions=updated_client_transactions,
            client_transaction_ids_to_ignore=[],
            cutoff_datetime=effective_datetime,
            key=PAYMENT_TYPE,
            value=payment_type,
        )

        # mustn't charge fees again for historic limit excesses
        remaining_limit = max(payment_type_limit - len(historic_withdrawals), 0)
        num_fees_to_incur = max(len(new_withdrawals) - remaining_limit, 0)

        if num_fees_to_incur > 0:
            total_fees_by_payment_type[payment_type] = num_fees_to_incur * payment_type_fee

    total_fee = sum(total_fees_by_payment_type.values())
    if total_fee > 0:
        instruction_detail = "Total fees charged for limits on payment types: "
        instruction_detail += ",".join(
            [
                fee_by_type[0] + " " + str(fee_by_type[1]) + " " + denomination
                for fee_by_type in total_fees_by_payment_type.items()
            ]
        )
        posting_instructions.extend(
            fees.fee_custom_instruction(
                customer_account_id=vault.account_id,
                denomination=denomination,
                amount=Decimal(total_fee),
                internal_account=payment_type_fee_income_account,
                instruction_details=utils.standard_instruction_details(
                    description=instruction_detail,
                    event_type="APPLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT_FEES",
                    gl_impacted=True,
                ),
            )
        )

    return posting_instructions
