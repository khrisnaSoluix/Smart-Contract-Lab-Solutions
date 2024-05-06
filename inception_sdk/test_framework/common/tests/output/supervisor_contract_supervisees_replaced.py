from contracts_api import SmartContractDescriptor, SupervisorContractEventType

api = "4.0.0"
version = "1.0.0"
supervised_smart_contracts = [
    SmartContractDescriptor(
        alias="us_checking",
        smart_contract_version_id="us_checking_account_ver_id",
        supervise_post_posting_hook=True,
    ),
    SmartContractDescriptor(
        alias="us_savings",
        smart_contract_version_id="us_savings_account_ver_id",
        supervise_post_posting_hook=False,
    ),
]
EVENT_WITH_SINGLE_TAG = "EVENT_WITH_SINGLE_TAG"
event_types = [
    SupervisorContractEventType(name=EVENT_WITH_SINGLE_TAG, scheduler_tag_ids=["E2E_AST_1"]),
    SupervisorContractEventType(
        name="EVENT_WITH_MULTIPLE_TAGS", scheduler_tag_ids=["E2E_PAUSED_TAG"]
    ),
    SupervisorContractEventType(name="EVENT_WITHOUT_TAGS", scheduler_tag_ids=["E2E_PAUSED_TAG"]),
]
