api = "3.11.0"
version = "1.0.0"

supervised_smart_contracts = [
    SmartContractDescriptor(
        alias="SUPERVISEE",
        smart_contract_version_id="1",
    ),
]

event_types = [
    EventType(
        name="SKIP_EVENT_TYPE", overrides_event_types=[("SUPERVISEE", "SUPERVISED_SKIP_EVENT_TYPE")]
    ),
]


def execution_schedules():
    return [
        ("SKIP_EVENT_TYPE", {"hour": "11", "minute": "30"}),
    ]


@requires(event_type="SKIP_EVENT_TYPE", supervisee_hook_directives="all")
def scheduled_code(event_type, effective_date):
    supervisee_vault = vault.supervisees["supervisee"]
    directives = supervisee_vault.get_hook_directives()
    for update_account_event_type_directive in directives.update_account_event_type_directives:
        supervisee_vault.update_event_type(
            event_type=update_account_event_type_directive.event_type,
            schedule=update_account_event_type_directive.schedule,
            skip=update_account_event_type_directive.skip,
        )


# flake8: noqa
