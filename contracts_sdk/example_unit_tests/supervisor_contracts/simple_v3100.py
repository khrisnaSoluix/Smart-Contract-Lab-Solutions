api = "3.10.0"
version = "1.0.0"

supervised_smart_contracts = [
    SmartContractDescriptor(alias="SUPERVISEE", smart_contract_version_id="1"),
]

event_types = [
    EventType(
        name="SUPERVISED_SCHEDULE_JOB_DETAILS",
        overrides_event_types=[
            ("SUPERVISEE", "SCHEDULE_JOB_DETAILS"),
        ],
    ),
]


@requires(event_type="SUPERVISED_SCHEDULE_JOB_DETAILS", supervisee_hook_directives="all")
def scheduled_code(event_type, effective_date):
    if event_type == "SUPERVISED_SCHEDULE_JOB_DETAILS":
        pause_datetime = vault.get_scheduled_job_details().pause_datetime

        supervisee_vault = vault.supervisees["SUPERVISEE"]
        supervisee_pause_datetime = supervisee_vault.get_scheduled_job_details().pause_datetime

        supervisee_vault.add_account_note(
            body=f"pause_datetime: {pause_datetime} {supervisee_pause_datetime}",
            note_type=NoteType.RAW_TEXT,
            is_visible_to_customer=True,
            date=effective_date,
        )


# flake8: noqa
