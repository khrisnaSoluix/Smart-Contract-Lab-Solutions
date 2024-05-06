# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# contracts api
from contracts_api import SmartContractDescriptor, SupervisorContractEventType

api = "4.0.0"
version = "1.0.0"

supervised_smart_contracts = [
    SmartContractDescriptor(
        alias="us_checking",
        smart_contract_version_id="&{us_checking_account}",
        supervise_post_posting_hook=True,
    ),
    # fmt: off
    # Turning off formatting to keep the alias on the same line as the SCVI
    SmartContractDescriptor(
        alias="us_savings",
        smart_contract_version_id="&{us_savings_account}",
        supervise_post_posting_hook=False,
    ),
    # fmt: on
]

EVENT_WITH_SINGLE_TAG = "EVENT_WITH_SINGLE_TAG"
event_types = [
    SupervisorContractEventType(
        name=EVENT_WITH_SINGLE_TAG,
        scheduler_tag_ids=["AST_1"],
    ),
    SupervisorContractEventType(
        name="EVENT_WITH_MULTIPLE_TAGS",
        scheduler_tag_ids=["AST_2", "AST_3"],
    ),
    SupervisorContractEventType(name="EVENT_WITHOUT_TAGS"),
]
