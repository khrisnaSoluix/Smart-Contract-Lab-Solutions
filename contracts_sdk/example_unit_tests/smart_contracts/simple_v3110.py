api = "3.11.0"
version = "1.0.0"


def execution_schedules():
    return [
        (
            "SKIP_EVENT_TYPE",
            {
                "minute": "*",
                "start_date": vault.get_account_creation_date().isoformat(),
                "end_date": (vault.get_account_creation_date() + timedelta(minutes=1)).isoformat(),
            },
        ),
    ]


def scheduled_code(event_type, effective_date):
    if event_type == "SKIP_EVENT_TYPE":
        vault.update_event_type(event_type="SKIP_EVENT_TYPE", skip=True)


# flake8: noqa
