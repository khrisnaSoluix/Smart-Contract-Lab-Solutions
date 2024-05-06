# standard libs
from datetime import datetime
from decimal import Decimal
from typing import Optional

# features
import library.features.common.common_parameters as common_parameters
import library.features.v4.common.fees as fees
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.deposit.deposit_interfaces as deposit_interfaces
import library.features.v4.lending.lending_addresses as lending_addresses

# contracts api
from contracts_api import DEFAULT_ADDRESS, BalanceDefaultDict, CustomInstruction

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault


def charge_partial_fee(
    vault: SmartContractVault,
    effective_datetime: datetime,
    fee_custom_instruction: CustomInstruction,
    fee_details: deposit_interfaces.PartialFeeCollection,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    available_balance_feature: Optional[deposit_interfaces.AvailableBalance] = None,
) -> list[CustomInstruction]:
    """
    Charge a Partial fee, intended to wrap an existing fee custom instruction.
    Fees are generally charged from a scheduled event.
    :param vault: Vault Object
    :param effective_datetime: the datetime at which to fetch the fee account parameters.
    :param fee_custom_instruction: The custom fee instruction to wrap
    :param fee_details: The associated fee details, implemented in a common feature definition
    :param balances: Account balances, if not provided then then balances will be retrieved using
    the EFFECTIVE_OBSERVATION_FETCHER_ID
    :param denomination: the denomination of the fee, if not provided the 'denomination' parameter
    is retrieved
    :param available_balance_feature: Interface to calculate the available balance for the account
    using a custom definition
    :return: A augmented list of CustomInstructions containing the partial fee instructions
    if required.
    """
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances

    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)

    incoming_fee_balances = fee_custom_instruction.balances(
        account_id=vault.account_id, tside=vault.tside
    )
    fee_amount = utils.balance_at_coordinates(
        balances=incoming_fee_balances,
        address=DEFAULT_ADDRESS,
        denomination=denomination,
    )
    # Fee amount is flipped as the fee amount pulls the change in the balance from the CI
    fee_amount = -fee_amount

    available_amount = (
        available_balance_feature.calculate(
            vault=vault, balances=balances, denomination=denomination
        )
        if available_balance_feature
        else utils.get_available_balance(balances=balances, denomination=denomination)
    )

    if available_amount >= fee_amount:
        return [fee_custom_instruction]
    chargeable_fee = min(fee_amount, available_amount)
    outstanding_fee = fee_amount - chargeable_fee
    partial_fee_address = fee_details.outstanding_fee_address
    fee_internal_account = fee_details.get_internal_account_parameter(
        vault=vault, effective_datetime=effective_datetime
    )

    custom_instructions: list[CustomInstruction] = []

    # modify instruction details
    incoming_fee_details = fee_custom_instruction.instruction_details
    if "description" in incoming_fee_details:
        incoming_fee_details["description"] += f" Partially charged, remaining {outstanding_fee}"
        " to be charged when the account has sufficient balance"
    else:
        incoming_fee_details["description"] = fee_details.fee_type
    if chargeable_fee > 0:
        custom_instructions.extend(
            fees.fee_custom_instruction(
                customer_account_id=vault.account_id,
                denomination=denomination,
                amount=chargeable_fee,
                customer_account_address=DEFAULT_ADDRESS,
                internal_account=fee_internal_account,
                instruction_details=incoming_fee_details,
            )
        )

    if outstanding_fee > 0:
        custom_instructions.extend(
            modify_tracking_balance(
                account_id=vault.account_id,
                denomination=denomination,
                tracking_address=partial_fee_address,
                fee_type=fee_details.fee_type,
                value=outstanding_fee,
            )
        )

    return custom_instructions


def charge_outstanding_fees(
    vault: SmartContractVault,
    effective_datetime: datetime,
    fee_collection: list[deposit_interfaces.PartialFeeCollection],
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    available_balance_feature: Optional[deposit_interfaces.AvailableBalance] = None,
) -> list[CustomInstruction]:
    """
    Charge outstanding fees is intended to be called from the post posting hook in order to address
    charging of outstanding partial amounts based on a pre-defined static repayment hierarchy.
    will reduce the tracking balance by the amount charged.
    :param vault: The SmartContractVault object,
    :param effective_datetime: the datetime at which to fetch the fee account parameter.
    :param fee_collection: The list of partial fees to collect from. The order will define
        the repayment hierarchy.
    :param balances: Account balances, if not provided then then balances will be retrieved using
    the LIVE_BALANCES_BOF_ID
    :param denomination: the denomination of the fee, if not provided the 'denomination' parameter
    is retrieved
    :param available_balance_feature: Interface to calculate the available balance for the account
    using a custom definition
    :return: a list of CustomInstructions to execute due to outstanding fees.
    """
    if balances is None:
        # Live balances are used here as this is intended to be called from the post-posting hook.
        balances = vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances
    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)

    custom_instructions: list[CustomInstruction] = []
    account_available_balance = (
        available_balance_feature.calculate(
            vault=vault, balances=balances, denomination=denomination
        )
        if available_balance_feature
        else utils.get_available_balance(balances=balances, denomination=denomination)
    )

    for fee in fee_collection:
        if account_available_balance <= Decimal("0"):
            break
        outstanding_fee_address = fee.outstanding_fee_address
        outstanding_fee_amount = utils.balance_at_coordinates(
            address=outstanding_fee_address, balances=balances, denomination=denomination
        )
        amount_to_charge = min(outstanding_fee_amount, account_available_balance)
        fee_internal_account = fee.get_internal_account_parameter(
            vault=vault, effective_datetime=effective_datetime
        )

        if amount_to_charge > Decimal("0"):
            custom_instructions.extend(
                fees.fee_custom_instruction(
                    customer_account_id=vault.account_id,
                    denomination=denomination,
                    amount=amount_to_charge,
                    customer_account_address=DEFAULT_ADDRESS,
                    internal_account=fee_internal_account,
                    instruction_details={
                        "description": f"Charge outstanding partial fee: {fee.fee_type}",
                        "event": f"Charge {fee.fee_type}",
                    },
                ),
            )
            custom_instructions.extend(
                modify_tracking_balance(
                    account_id=vault.account_id,
                    denomination=denomination,
                    tracking_address=outstanding_fee_address,
                    fee_type=fee.fee_type,
                    value=amount_to_charge,
                    payment_deduction=True,
                ),
            )
            account_available_balance -= amount_to_charge

    return custom_instructions


def has_outstanding_fees(
    vault: SmartContractVault,
    fee_collection: list[deposit_interfaces.PartialFeeCollection],
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> bool:
    """
    Check for any outstanding fees.
    This can be used in the Deactivation Hook to block account closure.

    :param vault: The SmartContractVault object
    :param fee_collection: The list of partial fees to collect from.
    :param balances: The balance that will be used for the fee calculations.
    Defaults to Live Balances if none provided.
    :param denomination: The denomination that the fees will be addressed in.
    Defaults to the Denomination Parameter Value.
    :return: True if any of the fees have an outstanding balance.
    """
    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)
    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances

    return any(
        utils.balance_at_coordinates(
            address=fee.outstanding_fee_address,
            balances=balances,
            denomination=denomination,
        )
        > Decimal(0)
        for fee in fee_collection
    )


def modify_tracking_balance(
    account_id: str,
    denomination: str,
    tracking_address: str,
    fee_type: str,
    value: Decimal,
    payment_deduction: bool = False,
) -> list[CustomInstruction]:
    instruction_details = {
        "description": fee_type,
        "event": f"Update {fee_type} amount owed",
    }
    return modify_tracking_balance_utils(
        account_id=account_id,
        denomination=denomination,
        tracking_address=tracking_address,
        value=value,
        payment_deduction=payment_deduction,
        instruction_details=instruction_details,
    )


# TODO: Move this to common utils
def modify_tracking_balance_utils(
    account_id: str,
    denomination: str,
    tracking_address: str,
    value: Decimal,
    payment_deduction: bool = False,
    instruction_details: dict = {},
) -> list[CustomInstruction]:
    """
    This function is intended to increase the tracking balance used for a partial payment address
    by a given value.

    To decrease the value on the tracking, set the payment_deduction argument to True to imply the
    tracking balance has been decreased due to the amount owed being paid.

    :param account_id: the account ID to modify the tracking balance for
    :param denomination: the denomination of the account.
    :param tracking_address: the Partial Payment Tracking Address
    :param fee_type: the description of the fee type.
    :param value: The amount to INCREASE the tracking balance by, or DECREASE if PAYMENT DEDUCTION
        is TRUE.
    :param payment_deduction: Whether or not to reverse the instruction by the amount.
    :return: returns the resulting custom instruction.
    """
    debit_address = lending_addresses.INTERNAL_CONTRA
    credit_address = tracking_address

    if value <= 0:
        return []

    # flip addresses if deducting from tracking balance due to a payment
    if payment_deduction:
        credit_address = debit_address
        debit_address = tracking_address

    return [
        CustomInstruction(
            postings=utils.create_postings(
                amount=value,
                debit_account=account_id,
                debit_address=debit_address,
                credit_account=account_id,
                credit_address=credit_address,
                denomination=denomination,
            ),
            instruction_details=instruction_details,
        )
    ]
