# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from typing import Optional

# features
import library.features.v4.common.accruals as accruals
import library.features.v4.common.addresses as common_addresses
import library.features.common.common_parameters as common_parameters
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.lending.interest_application as interest_application
import library.features.v4.lending.lending_addresses as lending_addresses

# contracts api
from contracts_api import (
    AccountIdShape,
    BalanceDefaultDict,
    CustomInstruction,
    Parameter,
    ParameterLevel,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

PARAM_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT = "capitalised_interest_receivable_account"
PARAM_CAPITALISED_INTEREST_RECEIVED_ACCOUNT = "capitalised_interest_received_account"
PARAM_CAPITALISED_PENALTIES_RECEIVED_ACCOUNT = "capitalised_penalties_received_account"
PARAM_CAPITALISE_PENALTY_INTEREST = "capitalise_penalty_interest"


capitalised_interest_receivable_account_param = Parameter(
    name=PARAM_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT,
    shape=AccountIdShape(),
    level=ParameterLevel.TEMPLATE,
    description="Internal account for unrealised capitalised interest receivable balance.",
    display_name="Capitalised Interest Receivable Account",
    default_value="CAPITALISED_INTEREST_RECEIVABLE",
)
capitalised_interest_received_account_param = Parameter(
    name=PARAM_CAPITALISED_INTEREST_RECEIVED_ACCOUNT,
    shape=AccountIdShape(),
    level=ParameterLevel.TEMPLATE,
    description="Internal account for capitalised interest received balance.",
    display_name="Capitalised Interest Received Account",
    default_value="CAPITALISED_INTEREST_RECEIVED",
)
capitalised_penalties_received_account_param = Parameter(
    name=PARAM_CAPITALISED_PENALTIES_RECEIVED_ACCOUNT,
    shape=AccountIdShape(),
    level=ParameterLevel.TEMPLATE,
    description="Internal account for capitalised penalties received balance.",
    display_name="Capitalised Penalties Received Account",
    default_value="CAPITALISED_PENALTIES_RECEIVED",
)
capitalise_penalty_interest_param = Parameter(
    name=PARAM_CAPITALISE_PENALTY_INTEREST,
    shape=common_parameters.BooleanShape,
    level=ParameterLevel.TEMPLATE,
    description="Determines if penalty interest is immediately added to Penalties (False) or "
    " accrued and capitalised at next due amount calculation.",
    display_name="Capitalise Penalty Interest",
    default_value=common_parameters.BooleanValueFalse,
)
parameters = [
    capitalised_interest_receivable_account_param,
    capitalised_interest_received_account_param,
    capitalised_penalties_received_account_param,
    capitalise_penalty_interest_param,
]


def is_capitalise_penalty_interest(vault: SmartContractVault) -> bool:
    return utils.get_parameter(
        vault=vault,
        name=PARAM_CAPITALISE_PENALTY_INTEREST,
        is_boolean=True,
    )


def handle_overpayments_to_penalties_pending_capitalisation(
    vault: SmartContractVault,
    denomination: str,
    balances: BalanceDefaultDict,
) -> list[CustomInstruction]:
    # only if there is balance in the address for amount pending capitalisation
    if (
        utils.balance_at_coordinates(
            balances=balances,
            address=lending_addresses.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
            denomination=denomination,
        )
        <= 0
    ):
        return []
    application_precision = interest_application.get_application_precision(vault=vault)
    capitalised_interest_received_account = get_capitalised_interest_received_account(vault=vault)
    capitalised_interest_receivable_account = get_capitalised_interest_receivable_account(
        vault=vault
    )
    return capitalise_interest(
        account_id=vault.account_id,
        application_precision=application_precision,
        balances=balances,
        capitalised_interest_receivable_account=capitalised_interest_receivable_account,
        capitalised_interest_received_account=capitalised_interest_received_account,
        denomination=denomination,
        interest_address_pending_capitalisation=lending_addresses.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,  # noqa: E501
        application_customer_address=common_addresses.DEFAULT,
    )


def handle_penalty_interest_capitalisation(
    vault: SmartContractVault,
    account_type: str,
) -> list[CustomInstruction]:
    if is_capitalise_penalty_interest(vault=vault):
        return handle_interest_capitalisation(
            vault=vault,
            account_type=account_type,
            # We have to override the EOD default as there will have been an accrual since EOD that
            # we need to include
            balances=vault.get_balances_observation(
                fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
            ).balances,
            interest_to_capitalise_address=lending_addresses.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,  # noqa: E501
        )

    return []


def handle_interest_capitalisation(
    vault: SmartContractVault,
    account_type: str,
    balances: Optional[BalanceDefaultDict] = None,
    interest_to_capitalise_address: str = lending_addresses.ACCRUED_INTEREST_PENDING_CAPITALISATION,
) -> list[CustomInstruction]:
    """
    Capitalises any accrued interest pending capitalisation interest after a repayment holiday ends.
    This may result in debit to PRINCIPAL and to the tracker balance for Capitalised
    Interest.
    This function needs running as frequently as the end of the repayment holiday needs detecting
    (e.g. run daily if you need to know by EOD) as we can't explicitly trigger any logic when a
    i.e. when a flag is removed (i.e. when a repayment holiday ends).

    :param vault: Vault object for the relevant account. Requires parameters, flags, balances
    :param account_type: The type of account, e.g. LOAN or MORTGAGE
    :param balances: Balances to use. Defaults to EOD balances
    :param interest_to_capitalise_address: the address that the interest to capitalise is held at
    :param is_penalty_interest_capitalisation: whether or not it is penalty interest being
    capitalised
    :return: posting instructions to capitalise the interest
    """
    balances = (
        balances or vault.get_balances_observation(fetcher_id=fetchers.EOD_FETCHER_ID).balances
    )
    denomination = _get_denomination(vault=vault)
    capitalised_interest_received_account = get_capitalised_interest_received_account(vault=vault)
    capitalised_interest_receivable_account = get_capitalised_interest_receivable_account(
        vault=vault
    )
    application_precision = interest_application.get_application_precision(vault=vault)

    return capitalise_interest(
        account_id=vault.account_id,
        application_precision=application_precision,
        balances=balances,
        capitalised_interest_receivable_account=capitalised_interest_receivable_account,
        capitalised_interest_received_account=capitalised_interest_received_account,
        denomination=denomination,
        interest_address_pending_capitalisation=interest_to_capitalise_address,
        account_type=account_type,
    )


def capitalise_interest(
    account_id: str,
    application_precision: int,
    balances: BalanceDefaultDict,
    capitalised_interest_receivable_account: str,
    capitalised_interest_received_account: str,
    denomination: str,
    interest_address_pending_capitalisation: str,
    account_type: str = "",
    application_customer_address: str = lending_addresses.PRINCIPAL,
) -> list[CustomInstruction]:
    """
    Create postings to apply any accrued interest pending capitalisation and track capitalised
    amount. Uses standard accrual posting format for application
    """

    event_type = "END_OF_REPAYMENT_HOLIDAY"

    accrued_capitalised_interest = utils.balance_at_coordinates(
        balances=balances,
        address=interest_address_pending_capitalisation,
        denomination=denomination,
    )
    interest_to_apply = utils.round_decimal(
        amount=accrued_capitalised_interest, decimal_places=application_precision
    )

    if interest_to_apply <= 0:
        return []
    else:
        postings = accruals.accrual_application_postings(
            customer_account=account_id,
            denomination=denomination,
            accrual_amount=accrued_capitalised_interest,
            application_amount=interest_to_apply,
            accrual_customer_address=interest_address_pending_capitalisation,
            accrual_internal_account=capitalised_interest_receivable_account,
            # TODO override to DEFAULT for early repayment
            application_customer_address=application_customer_address,
            application_internal_account=capitalised_interest_received_account,
            payable=False,
        ) + utils.create_postings(
            amount=interest_to_apply,
            debit_account=account_id,
            credit_account=account_id,
            debit_address=lending_addresses.CAPITALISED_INTEREST_TRACKER,
            credit_address=common_addresses.INTERNAL_CONTRA,
        )

        return [
            CustomInstruction(
                postings=postings,
                instruction_details={
                    "description": "Capitalise interest accrued to principal",
                    "event": event_type,
                    "gl_impacted": "True",
                    "account_type": account_type,
                },
            )
        ]


def _get_denomination(vault: SmartContractVault, denomination: Optional[str] = None) -> str:
    """
    Get the denomination of the account, allowing for a None to be passed in.

    :param vault: vault object for the relevant account
    :param denomination: denomination of the relevant loan
    :return: the denomination
    """
    return (
        utils.get_parameter(vault=vault, name="denomination")
        if denomination is None
        else denomination
    )


def get_capitalised_interest_received_account(vault: SmartContractVault) -> str:
    return utils.get_parameter(vault=vault, name=PARAM_CAPITALISED_INTEREST_RECEIVED_ACCOUNT)


def get_capitalised_interest_receivable_account(vault: SmartContractVault) -> str:
    return utils.get_parameter(vault=vault, name=PARAM_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT)
