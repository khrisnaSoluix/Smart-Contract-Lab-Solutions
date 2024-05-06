# standard libs
from decimal import Decimal
from typing import Optional

# features
import library.features.v4.common.utils as utils
import library.features.v4.lending.lending_interfaces as lending_interfaces
import library.features.v4.lending.payments as payments

# contracts api
from contracts_api import (
    BalanceDefaultDict,
    CustomInstruction,
    NumberShape,
    Parameter,
    ParameterLevel,
    Posting,
    Rejection,
    RejectionReason,
    Tside,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# addresses
PARAM_AVAILABLE_REDRAW_FUNDS = "available_redraw_funds"
REDRAW_ADDRESS = "REDRAW"

derived_parameters = [
    Parameter(
        name=PARAM_AVAILABLE_REDRAW_FUNDS,
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="Total available redraw funds",
        display_name="Available Redraw Funds",
    ),
]


def handle_overpayment(
    vault: SmartContractVault,
    overpayment_amount: Decimal,
    denomination: str,
    balances: Optional[BalanceDefaultDict] = None,
) -> list[Posting]:
    """Handle overpayments by rebalancing the amount to the REDRAW address
    :param vault: the vault object for the account receiving the overpayment
    :param overpayment_amount: the amount being overpaid
    :param denomination: the denomination of the overpayment
    :param balances: unused, but required to satisfy the overpayment interface
    :return: postings to handle the overpayment
    """

    return utils.create_postings(
        debit_account=vault.account_id,
        denomination=denomination,
        amount=overpayment_amount,
        credit_account=vault.account_id,
        credit_address=REDRAW_ADDRESS,
    )


OverpaymentFeature = lending_interfaces.Overpayment(handle_overpayment=handle_overpayment)


def auto_repayment(
    balances: BalanceDefaultDict,
    due_amount_posting_instructions: list[CustomInstruction],
    denomination: str,
    account_id: str,
    repayment_hierarchy: list[str],
) -> list[CustomInstruction]:
    """
    Creates posting instructions to automatically repay due balances from the redraw balance

    :param balances: The balances that include the current redraw balance
    :param due_amount_posting_instructions: The postings for any due amounts
    to be committed to the ledger
    :param denomination: The denomination of the account
    :param account_id: The id of the account
    :param repayment_hierarchy: Order in which a repayment amount is to be
    distributed across due addresses
    :return: The custom instructions that automatically repay any due balances
    """
    redraw_balance = utils.balance_at_coordinates(
        balances=balances, address=REDRAW_ADDRESS, denomination=denomination
    )

    if redraw_balance >= Decimal("0") or not due_amount_posting_instructions:
        return []

    # get a map of due addresses to due amounts
    # e.g. {"PRINCIPAL_DUE": Decimal("60"), "INTEREST_DUE": Decimal("20")}
    due_amount_mapping = {}
    for due_instruction in due_amount_posting_instructions:
        balance_dict = due_instruction.balances(account_id=account_id, tside=Tside.ASSET)
        for balance in balance_dict.keys():
            if balance.account_address in repayment_hierarchy:
                due_amount_mapping.update({balance.account_address: balance_dict[balance].net})

    auto_repayment_postings: list[Posting] = []
    remaining_redraw_balance = abs(redraw_balance)
    for address in repayment_hierarchy:
        if remaining_redraw_balance == Decimal("0"):
            break

        repayment_amount = min(
            remaining_redraw_balance, due_amount_mapping.get(address, Decimal("0"))
        )
        if repayment_amount > Decimal("0"):
            auto_repayment_postings += payments.redistribute_postings(
                debit_account=account_id,
                denomination=denomination,
                amount=repayment_amount,
                credit_account=account_id,
                credit_address=address,
                debit_address=REDRAW_ADDRESS,
            )
            remaining_redraw_balance -= repayment_amount

    if auto_repayment_postings:
        return [
            CustomInstruction(
                postings=auto_repayment_postings,
                instruction_details={
                    "description": "Auto repay due balances from the redraw balance",
                    "event": "PROCESS_AUTO_REPAYMENT_FROM_REDRAW_BALANCE",
                },
                override_all_restrictions=True,
            )
        ]
    return []


def get_available_redraw_funds(balances: BalanceDefaultDict, denomination: str) -> Decimal:
    """
    Returns the available redraw amount

    :param balances: The current balances for the loan account
    which should include the redraw balance
    :param denomination: The denomination of the account
    :return: The remaining amount in the redraw balance (always positive)
    """
    return abs(
        utils.balance_at_coordinates(
            balances=balances, address=REDRAW_ADDRESS, denomination=denomination, decimal_places=2
        )
    )


def reject_closure_when_outstanding_redraw_funds(
    balances: BalanceDefaultDict, denomination: str
) -> Optional[Rejection]:
    """
    Returns a rejection if the redraw balance still contains funds

    :param balances: The current balances for the loan account
    which should include the redraw balance
    :param denomination: The denomination of the account
    :return: A rejection if the redraw balance contains a non-zero amount
    """
    if utils.balance_at_coordinates(
        balances=balances, address=REDRAW_ADDRESS, denomination=denomination
    ) != Decimal("0"):
        return Rejection(
            message="The loan cannot be closed until all remaining redraw funds are cleared.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None


def validate_redraw_funds(
    balances: BalanceDefaultDict,
    posting_amount: Decimal,
    denomination: str,
) -> Optional[Rejection]:
    """
    Reject a posting if the withdrawal amount is greater than the current redraw balance.

    :param balances: The balances, which should contain the balances for the redraw address
    :param posting_amount: The amount to validate against the current redraw amount
    :param denomination: The denomination of the posting
    """
    redraw_balance = utils.balance_at_coordinates(
        balances=balances, address=REDRAW_ADDRESS, denomination=denomination
    )

    if posting_amount > 0 and posting_amount > abs(redraw_balance):
        return Rejection(
            message=f"Transaction amount {posting_amount} {denomination} is greater than "
            f"the available redraw funds of {abs(redraw_balance)} {denomination}.",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )

    return None
