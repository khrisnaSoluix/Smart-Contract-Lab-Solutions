# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
# standard libs
from dataclasses import dataclass
from enum import Enum


class AccountStatus(Enum):
    ACCOUNT_STATUS_UNKNOWN = "ACCOUNT_STATUS_UNKNOWN"
    ACCOUNT_STATUS_OPEN = "ACCOUNT_STATUS_OPEN"
    ACCOUNT_STATUS_CLOSED = "ACCOUNT_STATUS_CLOSED"
    ACCOUNT_STATUS_CANCELLED = "ACCOUNT_STATUS_CANCELLED"
    ACCOUNT_STATUS_PENDING_CLOSURE = "ACCOUNT_STATUS_PENDING_CLOSURE"
    ACCOUNT_STATUS_PENDING = "ACCOUNT_STATUS_PENDING"


class AccountUpdateType(Enum):
    INSTANCE_PARAM_VALS_UPDATE = "instance_param_vals_update"
    PRODUCT_VERSION_UPDATE = "product_version_update"
    ACTIVATION_UPDATE = "activation_update"
    CLOSURE_UPDATE = "closure_update"


@dataclass
class CreateAccountEvent:
    """
    This class represents a create account event that can be consumed by the Simulation
    endpoint to instruct the creation of a new account
    Please note that `.to_dict()` must be called when the object is passed into vault_caller.

    Args:
        param id: a unique ID for an account. Optional for create requests.
        param product_version_id: the ID of the product the account is associated with.
                        Can be obtained using the /v1/products endpoint.
                        Required for create requests if product_version_id is not provided.
        permitted_denominations: Denominations the account can hold balances in.
                        Must be a subset of the denominations supported by the product version.
        status: The status of the account.
        stakeholder_ids: The customer IDs that can access the account. Required for create requests.
        instance_param_vals: The instance-level parameters for the associated product;
                                a map of the parameter name to value.
        derived_instance_param_vals:
            The derived instance-level parameters for the associated product
            that have been defined in the account's Smart Contract code;
            a map of the parameter name to value.
        details: A map of unstructured fields that hold instance-specific account details,
                for example, the source of funds.
    """

    id: str  # noqa: A003
    product_version_id: str
    permitted_denominations: list[str] | None
    status: AccountStatus
    stakeholder_ids: list[str]
    instance_param_vals: dict
    derived_instance_param_vals: dict
    details: dict

    def to_dict(self):
        return {"create_account": self.__dict__}


@dataclass
class CreateAccountUpdateEvent:
    """
    This class represents the base event for making an account update.
    Please note that `.to_dict()` must be called when the object is passed into vault_caller.

    Args:
        param account_id: id of account to update.
        param update_type: the type of update to be made on account_id. Must be one of the
                           following:
                               - instance_param_vals_update
                               - product_version_update
                               - activation_update
                               - closure_update
        param update_payload: payload for the given update_type
    """

    account_id: str
    update_type: AccountUpdateType
    update_payload: dict

    def to_dict(self):
        return {
            "create_account_update": {
                "account_id": self.account_id,
                f"{self.update_type.value}": self.update_payload,
            }
        }


class CreateInstanceParameterUpdateEvent(CreateAccountUpdateEvent):
    """
    This class represents the event for updating the instance parameter value of an account.
    Please note that `.to_dict()` must be called when the object is passed into vault_caller.

    Args:
        param account_id: id of account to update.
        param update_payload: payload for the account update. Must be map of parameter name to value
    """

    account_id: str
    update_payload: dict

    def __init__(self, account_id, update_payload):
        super().__init__(
            account_id,
            AccountUpdateType.INSTANCE_PARAM_VALS_UPDATE,
            {"instance_param_vals": update_payload},
        )


class CreateAccountProductVersionUpdateEvent(CreateAccountUpdateEvent):
    """
    This class represents the event for updating the product version of an account.
    Please note that `.to_dict()` must be called when the object is passed into vault_caller.
    Also note that the updated product version ID is assumed to be already initialised
    as part of the test set up.

    Args:
        param account_id: id of account to update.
        param product_version_id: id of the product version we're updating to.
    """

    account_id: str
    product_version_id: dict

    def __init__(self, account_id, product_version_id):
        super().__init__(
            account_id,
            AccountUpdateType.PRODUCT_VERSION_UPDATE,
            {"product_version_id": product_version_id},
        )


@dataclass
class UpdateAccountEvent:
    """
    This class represents the base event for making an update account event.
    Please note that `.to_dict()` must be called when the object is passed into vault_caller.

    Args:
        param account_id: id of account to update.
        param status: account status.
    """

    account_id: str
    status: AccountStatus

    def to_dict(self):
        return {"update_account": {"id": self.account_id, "status": self.status.value}}
