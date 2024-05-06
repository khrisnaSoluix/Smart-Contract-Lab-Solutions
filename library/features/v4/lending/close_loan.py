# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.

# standard libs
from decimal import Decimal
from typing import Optional

# features
import library.features.v4.common.utils as utils
import library.features.v4.lending.lending_addresses as lending_addresses
import library.features.v4.lending.lending_interfaces as lending_interfaces

# contracts api
from contracts_api import (
    AccountNotificationDirective,
    BalanceDefaultDict,
    CustomInstruction,
    Posting,
    Rejection,
    RejectionReason,
    Tside,
)

# Notifications
LOAN_PAID_OFF_NOTIFICATION_SUFFIX = "_LOAN_PAID_OFF"

# address groups
DUE_ADDRESSES = [lending_addresses.PRINCIPAL_DUE, lending_addresses.INTEREST_DUE]
OVERDUE_ADDRESSES = [lending_addresses.PRINCIPAL_OVERDUE, lending_addresses.INTEREST_OVERDUE]
PENALTIES_ADDRESSES = [lending_addresses.PENALTIES]
PRINCIPAL_ADDRESSES = [lending_addresses.PRINCIPAL]

PAYMENT_ADDRESSES = OVERDUE_ADDRESSES + PENALTIES_ADDRESSES + DUE_ADDRESSES
DEBT_ADDRESSES = PAYMENT_ADDRESSES + PRINCIPAL_ADDRESSES


def notification_type(product_name: str) -> str:
    """
    Creates the notification type
    :param product_name: The product name
    :return: str
    """
    return f"{product_name.upper()}{LOAN_PAID_OFF_NOTIFICATION_SUFFIX}"


def does_repayment_fully_repay_loan(
    repayment_posting_instructions: list[CustomInstruction],
    balances: BalanceDefaultDict,
    denomination: str,
    account_id: str,
    debt_addresses: Optional[list[str]] = None,
    payment_addresses: Optional[list[str]] = None,
) -> bool:
    """
    Determines whether the repayment posting instructions fully repay the outstanding debt
    on the loan

    :param repayment_posting_instructions: The repayment posting instructions
    :param balances: The current balances used to check the outstanding debt
    :param denomination: The denomination of the account and the repayment
    :param account_id: The id of the account the repayment is for
    :param debt_addresses: The balance addresses that hold the debt for the account
    :param payment_addresses: The balance addresses that are expected to be paid off during
    the lifecycle of the account
    :return: A boolean that indicates whether the repayment has paid off the loan
    """
    if debt_addresses is None:
        debt_addresses = DEBT_ADDRESSES
    if payment_addresses is None:
        payment_addresses = PAYMENT_ADDRESSES

    outstanding_debt = utils.sum_balances(
        balances=balances,
        addresses=debt_addresses,
        denomination=denomination,
    )

    merged_repayment_balances = BalanceDefaultDict()
    for posting_instruction in repayment_posting_instructions:
        merged_repayment_balances += posting_instruction.balances(
            account_id=account_id, tside=Tside.ASSET
        )

    # It is always assumed that repayment_posting_instructions contain the posting instructions
    # to pay off the balance(s) in the list of payment addresses, and so the sum of the balance(s)
    # in the payment address list gives the total amount repaid.
    repayment_amount = abs(
        utils.sum_balances(
            balances=merged_repayment_balances,
            addresses=payment_addresses,
            denomination=denomination,
        )
    )
    return repayment_amount >= outstanding_debt


# notification helpers
def send_loan_paid_off_notification(
    account_id: str,
    product_name: str,
) -> AccountNotificationDirective:
    """
    Instruct a loan paid off notification.

    :param account_id: vault account id
    :param product_name: the name of the product for the notification prefix
    :return: AccountNotificationDirective
    """
    return AccountNotificationDirective(
        notification_type=notification_type(product_name),
        notification_details={
            "account_id": account_id,
        },
    )


def net_balances(
    balances: BalanceDefaultDict,
    denomination: str,
    account_id: str,
    residual_cleanup_features: Optional[list[lending_interfaces.ResidualCleanup]] = None,
) -> list[CustomInstruction]:
    """
    Nets off the EMI, and any other accounting addresses from other features, that should be
    cleared before the loan is closed

    :param balances: The current balances for the account
    :param denomination: The denomination of the account
    :param account_id: The id of the account
    :param residual_cleanup_features: list of features to get residual cleanup postings
    :return: A list of custom instructions used to net all remaining balances
    """
    net_postings: list[Posting] = []
    emi_amount = utils.balance_at_coordinates(
        balances=balances, address=lending_addresses.EMI, denomination=denomination
    )

    if emi_amount > Decimal("0"):
        net_postings += utils.create_postings(
            amount=emi_amount,
            debit_account=account_id,
            credit_account=account_id,
            debit_address=lending_addresses.INTERNAL_CONTRA,
            credit_address=lending_addresses.EMI,
            denomination=denomination,
        )

    if residual_cleanup_features is not None:
        for feature in residual_cleanup_features:
            net_postings += feature.get_residual_cleanup_postings(
                balances=balances, account_id=account_id, denomination=denomination
            )

    posting_instructions: list[CustomInstruction] = []
    if net_postings:
        posting_instructions += [
            CustomInstruction(
                postings=net_postings,
                instruction_details={
                    "description": "Clearing all residual balances",
                    "event": "END_OF_LOAN",
                },
            )
        ]
    return posting_instructions


def reject_closure_when_outstanding_debt(
    balances: BalanceDefaultDict,
    denomination: str,
    debt_addresses: list[str] = DEBT_ADDRESSES,
) -> Optional[Rejection]:
    """
    Returns a rejection if the debt addresses sum to a non-zero amount

    :param balances: The current balances for the loan account
    :param denomination: The denomination of the account
    :param debt_addresses: A list of debt addresses to sum
    :return: A rejection if the debt addresses sum to a non-zero value
    """
    if utils.sum_balances(
        balances=balances,
        addresses=debt_addresses,
        denomination=denomination,
    ) != Decimal("0"):
        return Rejection(
            message="The loan cannot be closed until all outstanding debt is repaid",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None
