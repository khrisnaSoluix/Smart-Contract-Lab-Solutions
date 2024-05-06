# CBF: Supported Denominations

"""
Provides commonly used Contracts API v4 deposit helper methods for use with smart contracts
"""
# standard libs
from decimal import Decimal
from typing import Optional

# features
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import BalanceDefaultDict, Rejection, RejectionReason


def validate(
    balances: BalanceDefaultDict,
    denominations: list[str],
    posting_instructions: utils.PostingInstructionListAlias,
) -> Optional[Rejection]:
    """
    Returns rejection if the posting instructions balance is gt available balance for each
    denomination. Logic applies only on withdrawal and for Tside.LIABILITY

    :param balances: balances used to retrieve available balances
    :param denominations: list of denominations to check
    :param posting_instructions: list of posting instructions to process
    :return: the rejection of posting instruction amount exceeding available balance
    """
    for denomination in denominations:
        available_balance = utils.get_available_balance(
            balances=balances, denomination=denomination
        )

        posting_instruction_amount = Decimal(
            sum(
                utils.get_available_balance(
                    balances=posting_instruction.balances(), denomination=denomination
                )
                for posting_instruction in posting_instructions
            )
        )

        # posting_amount < 0 because deposits are accepted
        if posting_instruction_amount < 0 and abs(posting_instruction_amount) > available_balance:
            return Rejection(
                message=f"Posting amount of {abs(posting_instruction_amount)} {denomination} "
                f"is exceeding available balance of {available_balance} {denomination}.",
                reason_code=RejectionReason.INSUFFICIENT_FUNDS,
            )

    return None
