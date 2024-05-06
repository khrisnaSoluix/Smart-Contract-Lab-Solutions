# standard libs
from dataclasses import dataclass
from enum import Enum


class AccountPlanAssocStatus(Enum):
    ACCOUNT_PLAN_ASSOC_STATUS_UNKNOWN = "ACCOUNT_PLAN_ASSOC_STATUS_UNKNOWN"
    ACCOUNT_PLAN_ASSOC_STATUS_ACTIVE = "ACCOUNT_PLAN_ASSOC_STATUS_ACTIVE"
    ACCOUNT_PLAN_ASSOC_STATUS_INACTIVE = "ACCOUNT_PLAN_ASSOC_STATUS_INACTIVE"


@dataclass
class CreatePlanEvent:
    """
    This class represents a create plan event that can be consumed by the Simulation
    endpoint to instruct the creation of a plan
    Please note that `.to_dict()` must be called when the object is passed into vault_caller.

    Args:
        param id: A unique ID for a plan. Optional for create requests. Max length: 36 characters.
        param supervisor_contract_version_id: The ID of the supervisor contract version.
                                            Required for create requests.
    """

    id: str
    supervisor_contract_version_id: str

    def to_dict(self):
        return {"create_plan": self.__dict__}


@dataclass
class CreateAccountPlanAssocEvent:
    """
    This class represents a create plan event that can be consumed by the Simulation
    endpoint to instruct the creation of a plan
    Please note that `.to_dict()` must be called when the object is passed into vault_caller.

    Args:
        param id_for_account: A unique ID for an account.
            Optional for create requests. Max length: 36 characters.
        param account_id: The account ID associated with the plan.
        param plan_id: The plan ID associated with the account.
        param status: The status of the account plan association.
    """

    id: str
    account_id: str
    plan_id: str
    status: AccountPlanAssocStatus

    def to_dict(self):
        return {"create_account_plan_assoc": self.__dict__}
