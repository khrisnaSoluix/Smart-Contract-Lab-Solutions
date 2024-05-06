api = "3.10.0"
version = "1.0.0"

data_fetchers = [
    BalancesObservationFetcher(
        fetcher_id="lbof_1",
        at=DefinedDateTime.LIVE,
    ),
]


@fetch_account_data(event_type="FETCH_BALANCES_OBSERVATION", balances=["lbof_1"])
def scheduled_code(event_type, effective_date):
    if event_type == "SCHEDULE_JOB_DETAILS":
        pause_datetime = vault.get_scheduled_job_details().pause_datetime

        vault.add_account_note(
            body=f"pause_datetime: {pause_datetime}",
            note_type=NoteType.RAW_TEXT,
            is_visible_to_customer=True,
            date=effective_date,
        )
    elif event_type == "FETCH_BALANCES_OBSERVATION":
        live_balances_observation = vault.get_balances_observation(fetcher_id="lbof_1")
        live_balances_observations_net_balance = live_balances_observation.balances[
            (DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.COMMITTED)
        ].net

        vault.add_account_note(
            body=(
                f"live_balances_observation: {live_balances_observation.value_datetime}, "
                f"{live_balances_observations_net_balance}"
            ),
            note_type=NoteType.RAW_TEXT,
            is_visible_to_customer=True,
            date=effective_date,
        )


# flake8: noqa
