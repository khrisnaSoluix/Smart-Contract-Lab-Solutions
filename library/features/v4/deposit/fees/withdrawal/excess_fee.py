# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.

# CBF: Number of Withdrawals Permitted and Excess Withdrawal Fee

# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Optional

# features
import library.features.v4.common.client_transaction_utils as client_transaction_utils
import library.features.v4.common.fees as fees
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import (
    AccountIdShape,
    ClientTransaction,
    CustomInstruction,
    NumberShape,
    OptionalShape,
    OptionalValue,
    Parameter,
    ParameterLevel,
    StringShape,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# instruction detail key
INSTRUCTION_DETAIL_KEY = "TRANSACTION_TYPE"

# Parameters
PARAM_EXCESS_FEE = "excess_fee"
PARAM_PERMITTED_WITHDRAWALS = "permitted_withdrawals"
PARAM_EXCESS_FEE_MONITORED_TRANSACTION_TYPE = "excess_fee_monitored_transaction_type"
PARAM_EXCESS_FEE_ACCOUNT = "excess_fee_income_account"

parameters = [
    Parameter(
        name=PARAM_EXCESS_FEE,
        level=ParameterLevel.TEMPLATE,
        description="Fee charged for every withdrawal that exceeds the monthly withdrawal limit.",
        display_name="Excess Fee",
        shape=OptionalShape(shape=NumberShape(min_value=0, step=Decimal("0.01"))),
        default_value=OptionalValue(Decimal("0.00")),
    ),
    Parameter(
        name=PARAM_PERMITTED_WITHDRAWALS,
        level=ParameterLevel.TEMPLATE,
        description="Number of monthly permitted withdrawals. Please note that only transactions "
        "with the specified transaction type are counted towards this excess fee.",
        display_name="Permitted Withdrawals",
        shape=OptionalShape(shape=NumberShape(min_value=0, step=1)),
        default_value=OptionalValue(0),
    ),
    Parameter(
        name=PARAM_EXCESS_FEE_MONITORED_TRANSACTION_TYPE,
        level=ParameterLevel.TEMPLATE,
        description="Transaction type being monitored to determine how many operations of this type"
        " occurred in the current calendar month period. This parameter will only be used for the "
        " assessment of the excessive withdrawal fee.",
        display_name="Monitored Transaction Type",
        shape=OptionalShape(shape=StringShape()),
        default_value=OptionalValue(""),
    ),
    # Internal Account
    Parameter(
        name=PARAM_EXCESS_FEE_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for excess fee income balance.",
        display_name="Withdrawal Excess Fee Account",
        shape=AccountIdShape(),
        default_value="EXCESS_FEE_INCOME_ACCOUNT",
    ),
]


def apply(
    *,
    vault: SmartContractVault,
    proposed_client_transactions: dict[str, ClientTransaction],
    monthly_client_transactions: Optional[dict[str, ClientTransaction]] = None,
    effective_datetime: datetime,
    denomination: str,
    account_type: str = "",
) -> list[CustomInstruction]:
    """
    Check number of posting instructions have occurred month to date and return fees if the
    withdrawal limit has been exceeded.
    Only transactions with instruction details that has a key matching "INSTRUCTION_DETAIL_KEY"
    parameter, with a value matching "PARAM_MONITORED_TRANSACTION_TYPE" param are eligible for
    this excess withdrawal fee.

    :param vault: vault object used to retrieve parameters
    :param proposed_client_transactions: proposed client transactions to process
    :param monthly_client_transactions: monthly client transactions to process
    :param effective_datetime: datetime used to filter client transactions
    :param denomination: denomination used to filter posting instructions
    :param account_type: the account type
    :return: excess fee posting instructions
    """
    transaction_type: str = utils.get_parameter(
        vault, PARAM_EXCESS_FEE_MONITORED_TRANSACTION_TYPE, is_optional=True, default_value=""
    )
    if not transaction_type:
        return []
    filtered_proposed_posting_instructions = (
        client_transaction_utils.extract_debits_by_instruction_details_key(
            denomination=denomination,
            client_transactions=proposed_client_transactions,
            client_transaction_ids_to_ignore=[],
            cutoff_datetime=effective_datetime,
            key=INSTRUCTION_DETAIL_KEY,
            value=transaction_type,
        )
    )
    if not filtered_proposed_posting_instructions:
        return []

    excess_fee_amount = Decimal(
        utils.get_parameter(vault, PARAM_EXCESS_FEE, is_optional=True, default_value=0)
    )
    permitted_withdrawals = int(
        utils.get_parameter(vault, PARAM_PERMITTED_WITHDRAWALS, is_optional=True, default_value=-1)
    )
    if excess_fee_amount <= Decimal("0") or permitted_withdrawals < 0:
        return []

    if not monthly_client_transactions:
        monthly_client_transactions = vault.get_client_transactions(
            fetcher_id=fetchers.MONTH_TO_EFFECTIVE_POSTINGS_FETCHER_ID
        )

    filtered_monthly_posting_instructions = (
        client_transaction_utils.extract_debits_by_instruction_details_key(
            denomination=denomination,
            client_transactions=monthly_client_transactions,
            client_transaction_ids_to_ignore=list(proposed_client_transactions.keys()),
            cutoff_datetime=effective_datetime
            + relativedelta(day=1, hour=0, minute=0, second=0, microsecond=0),
            key=INSTRUCTION_DETAIL_KEY,
            value=transaction_type,
        )
    )

    current_withdrawals = len(filtered_monthly_posting_instructions)
    proposed_withdrawals = len(filtered_proposed_posting_instructions)
    proposed_exceeding_withdrawals = (
        proposed_withdrawals + current_withdrawals - permitted_withdrawals
    )

    if proposed_exceeding_withdrawals <= 0:
        return []

    # If withdrawals already exceeded then charge fee for every new withdrawal.
    if current_withdrawals > permitted_withdrawals:
        proposed_exceeding_withdrawals = proposed_withdrawals

    excess_fee_income_account = utils.get_parameter(vault, PARAM_EXCESS_FEE_ACCOUNT)
    return fees.fee_custom_instruction(
        customer_account_id=vault.account_id,
        denomination=denomination,
        amount=excess_fee_amount * proposed_exceeding_withdrawals,
        internal_account=excess_fee_income_account,
        instruction_details=utils.standard_instruction_details(
            description="Proposed withdrawals exceeded permitted "
            f"limit by {proposed_exceeding_withdrawals}",
            event_type="APPLY_EXCESS_FEES",
            gl_impacted=True,
            account_type=account_type,
        ),
    )
