from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Optional, NamedTuple

# inception lib
from inception_sdk.vault.contracts.types_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    PostingInstruction,
    Vault,
)
import library.features.common.utils as utils
import library.features.lending.interest_accrual as interest_accrual

all_parameters = [*interest_accrual.account_parameters]

# We should really genericise or import from debt_management, but some refactoring
# is needed to break unnecessary dependency cycles
APPLICATION_EVENT = "APPLY_ACCRUED_INTEREST"
INTEREST_DUE = "INTEREST_DUE"
INTERNAL_CONTRA = "INTERNAL_CONTRA"


# TODO INC-5684 update logic to invoke an api provided by interest_accrual feature
# to determine which address has been used for accrual (accrued_at_address), instead of
# being passed in by contract template
def get_application_posting_instructions(
    vault: Vault,
    effective_date: datetime,
    denomination: str,
    applied_to_address: str = INTEREST_DUE,
    accrued_at_address: str = interest_accrual.ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
    non_emi_accrued_at_address: str = interest_accrual.NON_EMI_ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
) -> list[PostingInstruction]:
    accrued_interest_receivable_account: str = utils.get_parameter(
        vault, "accrued_interest_receivable_account"
    )

    accrued_interest_raw_receivable = utils.get_balance_sum(
        vault,
        [accrued_at_address],
        denomination=denomination,
        timestamp=effective_date,
    )
    non_emi_accrued_interest_raw = utils.get_balance_sum(
        vault,
        [non_emi_accrued_at_address],
        denomination=denomination,
        timestamp=effective_date,
    )
    # by applying the rounded sum of both accrued interests and zeroing out all accrued interest
    # we avoid dealing with scenarios where the sum of rounded interest is greater than the
    # rounded sum of interest and we'd need to decide how this is then 'spread'
    total_interest_to_apply = utils.round_decimal(
        accrued_interest_raw_receivable + non_emi_accrued_interest_raw, decimal_places=2
    )
    posting_instructions = []
    if total_interest_to_apply > 0:
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=total_interest_to_apply,
                denomination=denomination,
                from_account_id=vault.account_id,
                from_account_address=applied_to_address,
                to_account_id=accrued_interest_receivable_account,
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id=f"APPLY_ACCRUED_INTEREST"
                f"_{vault.get_hook_execution_id()}_{denomination}_INTERNAL",
                instruction_details={
                    "description": "Interest Applied",
                    "event": APPLICATION_EVENT,
                },
            )
        )

    cleanup_instruction_details = {
        "description": "Zeroing remainder accrued interest after application",
        "event": APPLICATION_EVENT,
    }

    posting_instructions.extend(
        get_residual_cleanup_posting_instructions(
            vault,
            denomination,
            accrued_at_address=accrued_at_address,
            remainder=accrued_interest_raw_receivable,
            instruction_details=cleanup_instruction_details,
        )
    )
    posting_instructions.extend(
        get_residual_cleanup_posting_instructions(
            vault,
            denomination,
            accrued_at_address=non_emi_accrued_at_address,
            remainder=non_emi_accrued_interest_raw,
            instruction_details=cleanup_instruction_details,
        )
    )

    return posting_instructions


def get_residual_cleanup_posting_instructions(
    vault: Vault,
    denomination: str,
    instruction_details: Optional[dict[str, str]] = None,
    remainder: Optional[Decimal] = None,
    accrued_at_address: str = interest_accrual.ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
) -> list[PostingInstruction]:
    """
    Creates posting instructions to zero the net accrued interest address balance and reflect
    this on the relevant internal accounts. Typically used after applying accrued interest
    or when closing the account.
    The direction of the postings is based on the sign of the remainder (see param description).
    If application is greater than accrual, the postings are the same as a normal accrual:
    - debit accrued_at_address, credit INTERNAL_CONTRA (i.e. accrued_at_address balance increases)
    If application is less than accrual, the postings are a reversed accrual:
    - debit INTERNAL_CONTRA, credit accrued_at_address (i.e. accrued_at_address balance decreases)

    :param vault: used to fetch parameters and balances, and create posting instructions
    :param denomination: the denomination of the interest to clean up
    :param instruction_details: key-value-pairs to add to the returned posting instructions'
    instruction_details
    :param remainder: the remainder to zero out. This is signed and should be calculated as
    accrued interest - applied interest. For example, if using 2dp precision for application
    this might be 0.1244 - 0.12 (positive remainder) or 0.1264 - 0.13 (negative remainder)
    If not provided the fetched balance from the accrued_at_address is used instead.
    :param accrued_at_address: the balance address where accrued interest to zero out is held

    :return: the relevant posting instructions
    """
    instruction_details = instruction_details or {}
    posting_instructions: list[PostingInstruction] = []

    if remainder is None:
        remainder = utils.get_balance_sum(vault, [accrued_at_address])

    if remainder != 0:
        # For ASSET accounts, a negative remainder means we are applying more than accrued, so we
        # effectively need to accrue by abs(remainder amount) to zero the remainder
        cust_from_address = accrued_at_address if remainder < 0 else INTERNAL_CONTRA
        # a positive remainder means we are applying less than accrued, so we effectively need to
        # reverse accrue by abs(remainder amount) to zero the remainder
        cust_to_address = INTERNAL_CONTRA if remainder < 0 else accrued_at_address

        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=abs(remainder),
                denomination=denomination,
                from_account_id=vault.account_id,
                from_account_address=cust_from_address,
                to_account_id=vault.account_id,
                to_account_address=cust_to_address,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                # accrued_at_address is crucial to avoid CTI clashes as we may reverse both
                # emi and non-emi interest
                client_transaction_id=f"REVERSE_RESIDUAL_{accrued_at_address}_"
                f"{vault.get_hook_execution_id()}_{denomination}",
                instruction_details=instruction_details,
            )
        )
    return posting_instructions


# Renderer only strip out `Vault` from typehints, so we can't use it here directly yet
InterestApplication = NamedTuple(
    "InterestApplication",
    [
        ("all_parameters", list),
        (
            "get_residual_cleanup_posting_instructions",
            Callable[[Any, str, dict[str, str], Decimal, str], list[PostingInstruction]],
        ),
        (
            "get_application_posting_instructions",
            Callable[[Any, datetime, str, str, str], list[PostingInstruction]],
        ),
    ],
)

feature = InterestApplication(
    all_parameters=all_parameters,
    get_application_posting_instructions=get_application_posting_instructions,
    get_residual_cleanup_posting_instructions=get_residual_cleanup_posting_instructions,
)
