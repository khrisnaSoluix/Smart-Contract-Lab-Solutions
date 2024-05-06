# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.

# contracts api
from contracts_api import SmartContractEventType, SupervisorContractEventType

EVENT_TYPE_1 = "event_type_1"
EVENT_TYPE_2 = "event_type_2"
EVENT_TYPE_3 = "event_type_3"
EVENT_TYPE_4 = "event_type_4"
EVENT_TYPE_5 = "event_type_5"


def get_event_types(product_name: str):
    accrual_tags = [f"{product_name}_{EVENT_TYPE_1}_tag_1"]
    apply_tag = [f"{product_name}_{EVENT_TYPE_4}_tag_1", f"{product_name}_{EVENT_TYPE_4}_tag_2"]
    return [
        # We wouldn't normally mix and match these types, but for the purpose of our test it seems
        # acceptable
        SmartContractEventType(name=EVENT_TYPE_1, scheduler_tag_ids=accrual_tags),
        SmartContractEventType(name=EVENT_TYPE_2),
        SupervisorContractEventType(name=EVENT_TYPE_3),
        SupervisorContractEventType(name=EVENT_TYPE_4, scheduler_tag_ids=apply_tag),
        SupervisorContractEventType(
            name=EVENT_TYPE_5, overrides_event_types=[("a", EVENT_TYPE_5), ("b", EVENT_TYPE_5)]
        ),
    ]


# flake8: noqa
