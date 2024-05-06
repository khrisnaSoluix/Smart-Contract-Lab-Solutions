# standard libs
from datetime import datetime
from decimal import Decimal
from json import dumps
from typing import Optional, Union

# features
import library.features.common.common_parameters as common_parameters
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import (
    CustomInstruction,
    OutboundHardSettlement,
    Parameter,
    ParameterLevel,
    StringShape,
    Transfer,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

FEE_TYPE_METADATA_KEY = "fee_type"
FEES_ELIGIBLE_FOR_REBATE = "fees_eligible_for_rebate"
FEES_INELIGIBLE_FOR_REBATE = "fees_ineligible_for_rebate"
NON_FEE_POSTINGS = "non_fee_postings"

ELIGIBLE_POSTING_TYPES = [
    CustomInstruction.type,
    OutboundHardSettlement.type,
    Transfer.type,
]

PARAM_ELIGIBLE_FEE_TYPES = "fee_types_eligible_for_rebate"
PARAM_FEE_REBATE_INTERNAL_ACCOUNTS = "fee_rebate_internal_accounts"

parameters = [
    Parameter(
        name=PARAM_ELIGIBLE_FEE_TYPES,
        shape=StringShape(),
        level=ParameterLevel.TEMPLATE,
        description="The fee types eligible for rebate. "
        "Expects a string representation of a JSON list.",
        display_name="Eligible Fee Rebate Types",
        default_value=dumps(["out_of_network_atm"]),
    ),
    Parameter(
        name=PARAM_FEE_REBATE_INTERNAL_ACCOUNTS,
        shape=StringShape(),
        level=ParameterLevel.TEMPLATE,
        description="Mapping of fee type to fee rebate internal account. "
        "Expects a string representation of a JSON dictionary.",
        display_name="Eligible Fee Rebate Types",
        default_value=dumps({"out_of_network_atm": "ATM_FEE_REBATE_ACCOUNT"}),
    ),
]


def group_posting_instructions_by_fee_eligibility(
    vault: SmartContractVault,
    effective_datetime: datetime,
    proposed_posting_instructions: utils.PostingInstructionListAlias,
    denomination: Optional[str] = None,
) -> dict[str, utils.PostingInstructionListAlias]:
    """
    Used to allow products to provide the correct postings to relevant limit checks. This function
    will group the proposed posting instructions into three categories:
    1. Charged fees eligible for a rebate
    2. Charged fees ineligible for a rebate
    3. Non fee postings

    :param vault: Vault object
    :param effective_datetime: datetime the posting instructions are being processed
    :param proposed_posting_instructions: the proposed postings
    :param denomination: denomination of the account, defaults to None. If not provided the
    'denomination' parameter will be used
    :return: dict, with the keys 'eligible_for_rebate', 'non_rebate_eligible_fee' and
    'non_fee_postings'
    """
    fee_postings, non_fee_postings = _split_posting_instructions_into_fee_and_non_fee(
        posting_instructions=proposed_posting_instructions
    )

    if not fee_postings:
        return {
            NON_FEE_POSTINGS: non_fee_postings,
            FEES_ELIGIBLE_FOR_REBATE: [],
            FEES_INELIGIBLE_FOR_REBATE: [],
        }

    eligible_fee_types = _get_fee_types_eligible_for_rebate(
        vault=vault, effective_datetime=effective_datetime
    )
    fee_rebate_internal_accounts = _get_fee_rebate_internal_accounts(
        vault=vault, effective_datetime=effective_datetime
    )
    eligible_fee_postings: utils.PostingInstructionListAlias = []
    non_eligible_fee_postings: utils.PostingInstructionListAlias = []

    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)

    for posting in fee_postings:
        if is_posting_instruction_eligible_for_fee_rebate(
            posting_instruction=posting,
            eligible_fee_types=eligible_fee_types,
            fee_rebate_internal_accounts=fee_rebate_internal_accounts,
            denomination=denomination,
        ):
            eligible_fee_postings.append(posting)
        else:
            non_eligible_fee_postings.append(posting)

    return {
        NON_FEE_POSTINGS: non_fee_postings,
        FEES_ELIGIBLE_FOR_REBATE: eligible_fee_postings,
        FEES_INELIGIBLE_FOR_REBATE: non_eligible_fee_postings,
    }


def rebate_fees(
    vault: SmartContractVault,
    effective_datetime: datetime,
    posting_instructions: utils.PostingInstructionListAlias,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Generates fee rebate CustomInstructions, to be used in the post_posting_hook of a product

    :param vault: Vault object
    :param effective_datetime: datetime when the fees are charged
    :param posting_instructions: The accepted posting instructions
    :param denomination: denomination of the account, defaults to None. If not provided the
    'denomination' parameter is used.
    :return: the rebate CustomInstructions
    """

    eligible_fee_postings = group_posting_instructions_by_fee_eligibility(
        vault=vault,
        effective_datetime=effective_datetime,
        proposed_posting_instructions=posting_instructions,
        denomination=denomination,
    )[FEES_ELIGIBLE_FOR_REBATE]

    if not eligible_fee_postings:
        return []

    fee_rebate_internal_accounts = _get_fee_rebate_internal_accounts(
        vault=vault, effective_datetime=effective_datetime
    )

    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)

    return [
        CustomInstruction(
            postings=utils.create_postings(
                amount=_get_charged_fee_amount(
                    posting_instruction=posting, denomination=denomination  # type: ignore
                ),
                # One of the conditions to be eligible for a rebate is that the internal account
                # exists in the fee_rebate_internal_accounts parameter so we can access the key
                # directly without causing a KeyError()
                debit_account=fee_rebate_internal_accounts[
                    posting.instruction_details[FEE_TYPE_METADATA_KEY]
                ],
                credit_account=vault.account_id,
                denomination=denomination,
            ),
            # One of the conditions to be eligible for a rebate is that the fee type is present in
            # the instruction_details metadata so we can access the key directly without
            # causing a KeyError()
            instruction_details={
                "description": "Rebate charged fee, "
                f"{posting.instruction_details[FEE_TYPE_METADATA_KEY]}",
                "gl_impacted": "True",
            },
            override_all_restrictions=True,
        )
        for posting in eligible_fee_postings
    ]


def is_posting_instruction_eligible_for_fee_rebate(
    posting_instruction: utils.PostingInstructionTypeAlias,
    eligible_fee_types: list[str],
    fee_rebate_internal_accounts: dict[str, str],
    denomination: str,
) -> bool:

    if posting_instruction.type not in ELIGIBLE_POSTING_TYPES:
        return False
    # the posting type must be an eligible posting type, so we need to validate whether it is
    # in fact a debit (applicable to CustomInstruction and Transfer posting types only)
    if utils.get_current_debit_balance(
        balances=posting_instruction.balances(), denomination=denomination
    ) <= Decimal("0"):
        # The posting must be a credit and therefore we exit early
        return False

    fee_type = posting_instruction.instruction_details.get(FEE_TYPE_METADATA_KEY)
    if fee_type and fee_type in eligible_fee_types and fee_type in fee_rebate_internal_accounts:
        return True
    return False


def _split_posting_instructions_into_fee_and_non_fee(
    posting_instructions: utils.PostingInstructionListAlias,
) -> tuple[utils.PostingInstructionListAlias, utils.PostingInstructionListAlias]:
    fee_postings: utils.PostingInstructionListAlias = []
    non_fee_postings: utils.PostingInstructionListAlias = []
    for posting_instruction in posting_instructions:
        if FEE_TYPE_METADATA_KEY in posting_instruction.instruction_details:
            fee_postings.append(posting_instruction)
        else:
            non_fee_postings.append(posting_instruction)
    return fee_postings, non_fee_postings


def _get_charged_fee_amount(
    posting_instruction: Union[CustomInstruction, OutboundHardSettlement, Transfer],
    denomination: str,
) -> Decimal:
    """
    Returns the fee amount that has been charged. This function assumes that the posting instruction
    has already been filtered such that the posting_instruction.type exists within the
    ELIGIBLE_POSTING_TYPES
    """
    # multiply by -1 here since we expect the posting.balances() to return a -ve net amount since
    # this is a result of a debit posting
    return (
        utils.balance_at_coordinates(
            balances=posting_instruction.balances(), denomination=denomination
        )
        * -1
    )


def _get_fee_types_eligible_for_rebate(
    vault: SmartContractVault, effective_datetime: datetime
) -> list[str]:
    return utils.get_parameter(
        vault=vault, name=PARAM_ELIGIBLE_FEE_TYPES, at_datetime=effective_datetime, is_json=True
    )


def _get_fee_rebate_internal_accounts(
    vault: SmartContractVault, effective_datetime: datetime
) -> dict[str, str]:
    return utils.get_parameter(
        vault=vault,
        name=PARAM_FEE_REBATE_INTERNAL_ACCOUNTS,
        at_datetime=effective_datetime,
        is_json=True,
    )
