# standard libs
from datetime import datetime
from decimal import Decimal
from json import dumps
from typing import Optional

# features
import library.features.v4.common.account_tiers as account_tiers
import library.features.v4.common.addresses as common_addresses
import library.features.common.common_parameters as common_parameters
import library.features.v4.common.transaction_type_utils as transaction_type_utils
import library.features.v4.common.utils as utils
import library.features.v4.deposit.deposit_interfaces as deposit_interfaces

# contracts api
from contracts_api import (
    BalancesFilter,
    BalancesObservationFetcher,
    CustomInstruction,
    DefinedDateTime,
    Override,
    Parameter,
    ParameterLevel,
    RelativeDateTime,
    StringShape,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# Feature Addresses
DIRECT_DEPOSIT_TRACKING_ADDRESS = "DIRECT_DEPOSITS_TRACKER"

# Parameters
PARAM_DEPOSIT_THRESHOLD_BY_TIER = "deposit_threshold_by_tier"
parameters = [
    Parameter(
        name=PARAM_DEPOSIT_THRESHOLD_BY_TIER,
        level=ParameterLevel.TEMPLATE,
        description="The deposit threshold by account tier."
        "This is used as the minimum deposit amount for the WAIVE_FEE_CONDITION.",
        display_name="Deposit Threshold By Tier",
        shape=StringShape(),
        default_value=dumps(
            {
                "UPPER_TIER": "25",
                "MIDDLE_TIER": "75",
                "LOWER_TIER": "100",
            }
        ),
    ),
]

# Fetchers
DIRECT_DEPOSIT_EOD_FETCHER_ID = "EOD_FETCHER"
DIRECT_DEPOSIT_EOD_FETCHER = BalancesObservationFetcher(
    fetcher_id=DIRECT_DEPOSIT_EOD_FETCHER_ID,
    at=RelativeDateTime(
        origin=DefinedDateTime.EFFECTIVE_DATETIME, find=Override(hour=0, minute=0, second=0)
    ),
    filter=BalancesFilter(addresses=[DIRECT_DEPOSIT_TRACKING_ADDRESS]),
)

# Constants
DIRECT_DEPOSIT = "direct_deposit"


def generate_tracking_instructions(
    vault: SmartContractVault,
    posting_instructions: utils.PostingInstructionListAlias,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    This function generates instructions to track direct deposit transactions. This is
    to be used in the post_posting_hook. All incoming postings will have instruction details
    checked to include key: "type" and value: "direct_deposit". If matched the amount will
    be added to the tracking balance.

    :param vault: SmartContractVault object, used for getting denomination and account id
    :param posting_instructions: Posting instructions, usually the post posting hook args
    :param denomination: The value is fetched if not provided, defaults to None
    :return: If the direct deposit amount is greater than 0, the function will return
    instructions to update the tracking address
    """
    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)

    total_deposit_amount = Decimal(0)
    for posting_instruction in posting_instructions:
        if transaction_type_utils.match_transaction_type(
            posting_instruction=posting_instruction,
            values=[DIRECT_DEPOSIT],
        ):
            posting_balances = posting_instruction.balances()
            deposit_value = utils.balance_at_coordinates(
                balances=posting_balances, denomination=denomination
            )
            total_deposit_amount += deposit_value

    if total_deposit_amount > Decimal("0"):
        return [
            CustomInstruction(
                postings=utils.create_postings(
                    amount=total_deposit_amount,
                    debit_account=vault.account_id,
                    debit_address=common_addresses.INTERNAL_CONTRA,
                    credit_account=vault.account_id,
                    credit_address=DIRECT_DEPOSIT_TRACKING_ADDRESS,
                    denomination=denomination,
                ),
                instruction_details=utils.standard_instruction_details(
                    description=f"Updating tracking balance with amount "
                    f"{total_deposit_amount} {denomination}.",
                    event_type="GENERATE_DEPOSIT_TRACKING_INSTRUCTIONS",
                ),
            )
        ]

    return []


def reset_tracking_instructions(
    vault: SmartContractVault,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    This function zeros out the direct deposit tracking address on an account. This is
    to be used in the scheduled_event_hook where appropriate (ie. after charging the
    monthly maintenance fee)

    :param vault: SmartContractVault object, used for getting denomination and account id
    :param denomination: The value is fetched if not provided, defaults to None
    :return: If the tracking address holds a balance greater than 0, the function will return
    instructions to zero out the tracking address
    """
    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)

    balances = vault.get_balances_observation(fetcher_id=DIRECT_DEPOSIT_EOD_FETCHER_ID).balances

    tracking_balance = utils.balance_at_coordinates(
        balances=balances,
        address=DIRECT_DEPOSIT_TRACKING_ADDRESS,
        denomination=denomination,
    )

    if tracking_balance > 0:
        return [
            CustomInstruction(
                postings=utils.create_postings(
                    amount=tracking_balance,
                    credit_account=vault.account_id,
                    credit_address=common_addresses.INTERNAL_CONTRA,
                    debit_account=vault.account_id,
                    debit_address=DIRECT_DEPOSIT_TRACKING_ADDRESS,
                    denomination=denomination,
                ),
                instruction_details=utils.standard_instruction_details(
                    description="Resetting tracking balance to 0.",
                    event_type="RESET_DEPOSIT_TRACKING_INSTRUCTIONS",
                ),
            )
        ]

    return []


def _is_deposit_tracking_address_above_threshold(
    vault: SmartContractVault,
    effective_datetime: datetime,
    denomination: Optional[str] = None,
) -> bool:
    # Threshold is a tier parameter driven by an account-level flag
    deposit_threshold_tiers = get_deposit_threshold_tiers_parameter(vault=vault)

    tier = account_tiers.get_account_tier(vault, effective_datetime)

    deposit_threshold = Decimal(
        account_tiers.get_tiered_parameter_value_based_on_account_tier(
            tiered_parameter=deposit_threshold_tiers,
            tier=tier,
            convert=Decimal,
        )
        or 0
    )

    if deposit_threshold > Decimal("0"):
        if denomination is None:
            denomination = common_parameters.get_denomination_parameter(vault=vault)

        balances = vault.get_balances_observation(fetcher_id=DIRECT_DEPOSIT_EOD_FETCHER_ID).balances

        tracking_balance = utils.balance_at_coordinates(
            balances=balances,
            address=DIRECT_DEPOSIT_TRACKING_ADDRESS,
            denomination=denomination,
        )

        if tracking_balance >= deposit_threshold:
            return True

    return False


def get_deposit_threshold_tiers_parameter(vault: SmartContractVault) -> dict[str, str]:
    return utils.get_parameter(vault, name=PARAM_DEPOSIT_THRESHOLD_BY_TIER, is_json=True)


WAIVE_FEE_AFTER_SUFFICIENT_DEPOSITS = deposit_interfaces.WaiveFeeCondition(
    waive_fees=_is_deposit_tracking_address_above_threshold
)
