# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from dataclasses import dataclass
from typing import Any


@dataclass
class CreateSmartContractModuleVersionsLink:
    """
    This class represents a Create Smart Contract Module Versions Link event that can be consumed
    by the Simulation endpoint to instruct the creation of a link between a smart contract and a
    contract module.
    Please note that `.to_dict()` must be called when the object is passed into vault_caller.

    Args:
        param id: id of the Link
        param smart_contract_version_id: The smart contract version ID this link relates to
        param alias_to_contract_module_version_id: Map of alias -> ContractModuleVersionID
            containing all contract module versions that should be linked to the smart contract
            version ID
    """

    id: str  # noqa: A003
    smart_contract_version_id: str
    alias_to_contract_module_version_id: dict

    def to_dict(self):
        return {"create_smart_contract_module_versions_link": self.__dict__}


@dataclass
class CreateTemplateParameterUpdateEvent:
    """
    This class represents the event for updating the template parameter value of an smart contract.
    Please note that `.to_dict()` must be called when the object is passed into vault_caller.
    """

    smart_contract_version_id: str
    parameter_name: str
    new_parameter_value: Any

    def to_dict(self):
        return {
            "update_smart_contract_param": {
                "smart_contract_version_id": self.smart_contract_version_id,
                "parameter_name": self.parameter_name,
                "new_parameter_value": self.new_parameter_value,
            }
        }
