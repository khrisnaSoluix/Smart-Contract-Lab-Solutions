# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from typing import Optional

# features
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import (
    SmartContractDescriptor,
    SupervisorActivationHookArguments,
    SupervisorContractEventType,
    SupervisorScheduledEventHookResult,
)

api = "4.0.0"
version = "1.0.0"

supervised_smart_contracts = [
    SmartContractDescriptor(
        alias="current_account",
        smart_contract_version_id="1",
    )
]

event_types = [
    SupervisorContractEventType(
        name="SUPERVISED_SERVICE_CHARGE",
        overrides_event_types=[("current_account", "SERVICE_CHARGE")],
    ),
]

event_types = [SupervisorContractEventType(name="name1", scheduler_tag_ids=["tag1"])]
event_types.append(SupervisorContractEventType(name="name2", scheduler_tag_ids=["tag2"]))
event_types += [SupervisorContractEventType(name="name3", scheduler_tag_ids=["tag3"])]
event_types[len(event_types) :] = [
    SupervisorContractEventType(name="name4", scheduler_tag_ids=["tag4"])
]


def activation_hook(vault, hook_arguments: SupervisorActivationHookArguments):
    now = datetime.now()
    utcnow = datetime.utcnow()
    return None


def scheduled_event_hook(vault, hook_arguments) -> Optional[SupervisorScheduledEventHookResult]:
    _scheduled_code_helper_function("")
    return None


def _scheduled_code_helper_function(event_type):
    if _scheduled_code_nested_helper_function(event_type):
        return len(event_type)


def _scheduled_code_nested_helper_function(event_type):
    return len(event_type)


def helper_1(vault):
    var = utils.get_parameter(vault, "parameter_name")


# flake8: noqa: F821
