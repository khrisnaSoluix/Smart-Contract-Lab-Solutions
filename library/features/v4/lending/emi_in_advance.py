# standard libs
from datetime import datetime
from decimal import Decimal

# features
import library.features.v4.common.events as events
import library.features.v4.common.utils as utils
import library.features.v4.lending.due_amount_calculation as due_amount_calculation
import library.features.v4.lending.emi as emi
import library.features.v4.lending.lending_interfaces as lending_interfaces

# contracts api
from contracts_api import CustomInstruction

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

EMI_IN_ADVANCE_OFFSET = 1

"""
This function should conceptually be part of EMI, but in order to avoid
accidental circular dependency in due calculation, it's pulled out independently
"""


def charge(
    vault: SmartContractVault,
    effective_datetime: datetime,
    amortisation_feature: lending_interfaces.Amortisation,
) -> list[CustomInstruction]:
    """
    Calculates emi and instructs postings for due amounts during account activation.
    Works only for zero interest products and thus instructs only principal_due postings
    :param vault: Vault object
    param effective_datetime: effective date of the charge
    :param amortisation_feature: contains the emi calculation method for the desired amortisation
    :return: list of custom instructions including emi and due transfer
    """
    custom_instructions: list[CustomInstruction] = []
    custom_instructions += emi.amortise(
        vault=vault,
        effective_datetime=effective_datetime,
        amortisation_feature=amortisation_feature,
    )

    principal: Decimal = utils.get_parameter(vault, name="principal")
    denomination: str = utils.get_parameter(vault, name="denomination")

    principal_due = amortisation_feature.calculate_emi(
        vault=vault,
        effective_datetime=effective_datetime,
        principal_amount=principal,
    )
    custom_instructions += [
        CustomInstruction(
            postings=due_amount_calculation.transfer_principal_due(
                customer_account=vault.account_id,
                principal_due=principal_due,
                denomination=denomination,
            ),
            instruction_details={
                "description": "Principal due on activation",
                "event": events.ACCOUNT_ACTIVATION,
            },
        )
    ]

    return custom_instructions
