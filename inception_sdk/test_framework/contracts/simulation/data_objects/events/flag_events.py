# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
# standard libs
from dataclasses import dataclass


@dataclass
class CreateFlag:
    """
    This class represents a Create Flag event that can be consumed by the Simulation
    endpoint to instruct the creation of a new account flag.
    Please note that `.to_dict()` must be called when the object is passed into vault_caller.

    Args:
        param flag_definition_id: id of the Flag defintion
        param effective_timestamp: isoformat string datetime of when the flag becomes effective
        param expiry_timestamp: isoformat string datetime of when the flag becomes ineffective
        param account_id: id of account the Flag to be created
    """

    flag_definition_id: str
    effective_timestamp: str
    expiry_timestamp: str
    account_id: str

    def to_dict(self):
        return {"create_flag": self.__dict__}


@dataclass
class CreateFlagDefinition:
    """
    This class represents creation of flag definition that can be consumed by the Simulation
    endpoint to instruct the creation of a new flag defintion.
    Please note that `.to_dict()` must be called when the object is passed into vault_caller.

    Args:
        param id: id of the Flag defintion to be created
    """

    id: str

    def to_dict(self):
        return {"create_flag_definition": self.__dict__}
