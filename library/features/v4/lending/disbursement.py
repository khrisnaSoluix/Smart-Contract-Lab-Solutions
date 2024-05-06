# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.

# standard libs
from decimal import Decimal

# features
import library.features.v4.common.utils as utils
import library.features.v4.lending.lending_addresses as lending_addresses

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    AccountIdShape,
    CustomInstruction,
    NumberShape,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    Phase,
    Posting,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

DISBURSEMENT_EVENT = "PRINCIPAL_DISBURSEMENT"
PARAM_PRINCIPAL = "principal"
PARAM_DEPOSIT_ACCOUNT = "deposit_account"

parameters = [
    Parameter(
        name=PARAM_PRINCIPAL,
        shape=NumberShape(min_value=Decimal("1")),
        level=ParameterLevel.INSTANCE,
        description="The agreed amount the customer will borrow from the bank.",
        display_name="Loan Principal",
        default_value=Decimal("1000"),
        # editable to support top-ups
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name=PARAM_DEPOSIT_ACCOUNT,
        shape=AccountIdShape(),
        level=ParameterLevel.INSTANCE,
        description="The account to which the principal borrowed amount will be transferred.",
        display_name="Deposit Account",
        default_value="00000000-0000-0000-0000-000000000000",
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
]


def get_principal_parameter(vault: SmartContractVault) -> Decimal:
    return Decimal(utils.get_parameter(vault=vault, name=PARAM_PRINCIPAL))


def get_deposit_account_parameter(vault: SmartContractVault) -> str:
    return str(utils.get_parameter(vault=vault, name=PARAM_DEPOSIT_ACCOUNT))


def get_disbursement_custom_instruction(
    account_id: str,
    deposit_account_id: str,
    principal: Decimal,
    denomination: str,
    principal_address: str = lending_addresses.PRINCIPAL,
) -> list[CustomInstruction]:
    return [
        CustomInstruction(
            postings=[
                Posting(
                    credit=False,
                    amount=principal,
                    denomination=denomination,
                    account_id=account_id,
                    account_address=principal_address,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    credit=True,
                    amount=principal,
                    denomination=denomination,
                    account_id=deposit_account_id,
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ],
            override_all_restrictions=True,
            instruction_details={
                "description": f"Principal disbursement of {principal}",
                "event": DISBURSEMENT_EVENT,
            },
        )
    ]
