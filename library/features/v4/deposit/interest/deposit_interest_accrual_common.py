# standard libs
from decimal import Decimal
from typing import Optional

# features
import library.features.v4.common.accruals as accruals
import library.features.common.common_parameters as common_parameters
import library.features.common.fetchers as fetchers
import library.features.v4.common.interest_accrual_common as interest_accrual_common
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import DEFAULT_ADDRESS, BalanceDefaultDict, CustomInstruction

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault


def get_accrual_capital(
    vault: SmartContractVault,
    *,
    balances: Optional[BalanceDefaultDict] = None,
    capital_addresses: Optional[list[str]] = None,
) -> Decimal:
    """
    Calculates the sum of balances at EOD that will be used to accrue interest on.

    :param vault: the vault object to use to for retrieving data and instructing directives
    :param balances: the balances to sum, EOD balances will be fetched if not provided
    :param capital_addresses: list of balance addresses that will be summed up to provide
    the amount to accrue interest on. Defaults to the DEFAULT_ADDRESS
    :return: the sum of balances on which interest will be accrued on
    """
    denomination = common_parameters.get_denomination_parameter(vault=vault)

    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers.EOD_FETCHER_ID).balances

    accrual_balance = utils.sum_balances(
        balances=balances,
        addresses=capital_addresses or [DEFAULT_ADDRESS],
        denomination=denomination,
    )

    # This is only used for deposit accruals, so we do not want to accrue on negative balances.
    return accrual_balance if accrual_balance > 0 else Decimal(0)


def get_interest_reversal_postings(
    *,
    vault: SmartContractVault,
    event_name: str,
    account_type: str = "",
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Reverse any accrued interest and apply back to the internal account.
    During account closure, any positively accrued interest that has not been applied
    should return back to the bank's internal account.

    :param vault: the vault object used to create interest reversal posting instructions
    :param event_name: the name of the event reversing any accrue interest
    :param account_type: the account type for GL purposes (e.g. to identify postings pertaining to
    current accounts vs savings accounts)
    :param balances: balances to pass through to function. If not passed in, defaults to None
    and the function will fetch balances using EFFECTIVE_OBSERVATION_FETCHER
    :param denomination:
    :return: the accrued interest reversal posting instructions
    """
    posting_instructions: list[CustomInstruction] = []

    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)

    balances = (
        balances
        or vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    )

    accrued_interest_payable_account = (
        interest_accrual_common.get_accrued_interest_payable_account_parameter(vault=vault)
    )
    accrued_interest_receivable_account = (
        interest_accrual_common.get_accrued_interest_receivable_account_parameter(vault=vault)
    )

    if accrued_interest_receivable := utils.sum_balances(
        balances=balances,
        addresses=[interest_accrual_common.ACCRUED_INTEREST_RECEIVABLE],
        denomination=denomination,
    ):
        posting_instructions.extend(
            accruals.accrual_custom_instruction(
                customer_account=vault.account_id,
                customer_address=interest_accrual_common.ACCRUED_INTEREST_RECEIVABLE,
                denomination=denomination,
                amount=abs(accrued_interest_receivable),
                internal_account=accrued_interest_receivable_account,
                payable=False,
                instruction_details=utils.standard_instruction_details(
                    description=f"Reversing {accrued_interest_receivable} {denomination} "
                    "of accrued interest",
                    event_type=event_name,
                    gl_impacted=True,
                    account_type=account_type,
                ),
                reversal=True,
            )
        )

    if accrued_interest_payable := utils.sum_balances(
        balances=balances,
        addresses=[interest_accrual_common.ACCRUED_INTEREST_PAYABLE],
        denomination=denomination,
    ):
        posting_instructions.extend(
            accruals.accrual_custom_instruction(
                customer_account=vault.account_id,
                customer_address=interest_accrual_common.ACCRUED_INTEREST_PAYABLE,
                denomination=denomination,
                amount=abs(accrued_interest_payable),
                internal_account=accrued_interest_payable_account,
                payable=True,
                instruction_details=utils.standard_instruction_details(
                    description=f"Reversing {accrued_interest_payable} {denomination} "
                    "of accrued interest",
                    event_type=event_name,
                    gl_impacted=True,
                    account_type=account_type,
                ),
                reversal=True,
            )
        )

    return posting_instructions


def get_target_customer_address_and_internal_account(
    *,
    vault: SmartContractVault,
    accrual_amount: Decimal,
    accrued_interest_payable_account: Optional[str] = None,
    accrued_interest_receivable_account: Optional[str] = None,
) -> tuple[str, str]:
    """
    Return the payable or receivable customer address and internal account based on the
    sign of the accrual amount

    :param vault: the vault object used to fetch parameter values
    :param accrual_amount: the amount of interest to accrue
    :param accrued_interest_payable_account: the accrued interest payable account, defaults
    to the value in the parameter if not provided
    :param accrued_interest_receivable_account: the accrued interest receivable account, defaults
    to the value in the parameter if not provided
    :return: target customer address, target internal account
    """
    if accrued_interest_payable_account is None:
        accrued_interest_payable_account = (
            interest_accrual_common.get_accrued_interest_payable_account_parameter(vault=vault)
        )
    if accrued_interest_receivable_account is None:
        accrued_interest_receivable_account = (
            interest_accrual_common.get_accrued_interest_receivable_account_parameter(vault=vault)
        )

    return (
        (interest_accrual_common.ACCRUED_INTEREST_PAYABLE, accrued_interest_payable_account)
        if accrual_amount >= 0
        else (
            interest_accrual_common.ACCRUED_INTEREST_RECEIVABLE,
            accrued_interest_receivable_account,
        )
    )
