api = "3.8.0"
version = "1.0.0"

supervised_smart_contracts = [
    SmartContractDescriptor(
        alias="SUPERVISEE", smart_contract_version_id="1", supervise_post_posting_hook=True
    ),
]

event_types = [
    EventType(
        name="CALENDAR_EVENT_TYPE",
        overrides_event_types=[("SUPERVISEE", "SUPERVISED_CALENDAR_EVENT_TYPE")],
    ),
    EventType(
        name="SUPERVISED_UPDATE_EVENT_TYPE",
        overrides_event_types=[
            ("SUPERVISEE", "UPDATE_EVENT_TYPE"),
        ],
    ),
]


def execution_schedules():
    return [
        ("EVENT_TYPE", {"hour": "11", "minute": "30"}),
    ]


@requires(event_type="CALENDAR_EVENT_TYPE", calendar=["A", "B"])
@requires(event_type="SUPERVISED_UPDATE_EVENT_TYPE", supervisee_hook_directives="all")
def scheduled_code(event_type, effective_date):
    supervisee_vault = vault.supervisees["supervisee"]
    if event_type == "CALENDAR_EVENT_TYPE":
        calendar_events = vault.get_calendar_events(calendar_ids=["A"])
        supervisee_vault.add_account_note(
            body=str(len(calendar_events)),
            note_type=NoteType.RAW_TEXT,
            date=effective_date,
            is_visible_to_customer=True,
        )

    if event_type == "SUPERVISED_UPDATE_EVENT_TYPE":
        directives = supervisee_vault.get_hook_directives()
        for update_account_event_type_directive in directives.update_account_event_type_directives:
            supervisee_vault.update_event_type(
                event_type=update_account_event_type_directive.event_type,
                schedule=update_account_event_type_directive.schedule,
                end_datetime=update_account_event_type_directive.end_datetime,
            )


def post_posting_code(postings, effective_date):
    for posting in postings:
        vault.supervisees[posting.account_id].add_account_note(
            body=f"Successfully created an account note for {posting.account_id}",
            note_type=NoteType.RAW_TEXT,
            is_visible_to_customer=True,
            date=effective_date,
        )


# flake8: noqa
